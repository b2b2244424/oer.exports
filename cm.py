# python collectiondbk2mobi.py -d test-ccap -o  result.html

import sys
import os
import Image
import shutil
from StringIO import StringIO
from tempfile import mkdtemp
import subprocess
import shutil

from lxml import etree
import urllib2

import module2dbk
import collection2dbk
import util

BASE_PATH = os.getcwd()
DEBUG=True

# XSL files
DOCBOOK2XHTML_XSL=util.makeXsl('dbk2xhtml.xsl')
DOCBOOK_CLEANUP_XSL = util.makeXsl('dbk-clean-whole.xsl')
DOCBOOK2OPF = util.makeXsl('dbk2mobiopf.xsl')

MODULES_XPATH = etree.XPath('//col:module/@document', namespaces=util.NAMESPACES)
IMAGES_XPATH = etree.XPath('//c:*/@src[not(starts-with(.,"http:"))]', namespaces=util.NAMESPACES)

def collection2mobi(collection_dir, output_xhtml, reduce_quality=False):

  p = util.Progress()

  collxml = etree.parse(os.path.join(collection_dir, 'collection.xml'))
  
  moduleIds = MODULES_XPATH(collxml)
  
  modules = {} # {'m1000': (etree.Element, {'file.jpg':'23947239874'})}
  allFiles = {}
  for moduleId in moduleIds:
    moduleDir = os.path.join(collection_dir, moduleId)
    if os.path.isdir(moduleDir):
      cnxml, files = loadModule(moduleDir)
      for f in files:
        allFiles[os.path.join(moduleId, f)] = files[f]

      modules[moduleId] = (cnxml, files)

  p.start(1, 'Converting collection to Docbook')
  dbk, newFiles = collection2dbk.convert(p, collxml, modules, collection_dir, svg2png=True, math2svg=True, reduce_quality=reduce_quality)#replace temp_dir with collection_dir
  allFiles.update(newFiles)
  
  p.tick('Converting Docbook to MOBI')
  stdErr = convert(p, dbk, allFiles, collection_dir, output_xhtml)
  p.finish()
  return stdErr


def loadModule(moduleDir):
  """ Given a directory of files (containing an index.cnxml) 
      load it into memory """
  # Try autogenerated CNXML 1st
  cnxmlPath = os.path.join(moduleDir, 'index_auto_generated.cnxml')
  if not os.path.exists(cnxmlPath):
    cnxmlPath = os.path.join(moduleDir, 'index.cnxml')
  cnxmlStr = open(cnxmlPath).read()
  cnxml = etree.parse(StringIO(cnxmlStr))
  files = {}
  for f in IMAGES_XPATH(cnxml):
    try:
      data = open(os.path.join(moduleDir, f)).read()
      files[f] = data
      #print >> sys.stderr, "LOG: Image ADDED! %s %s" % (module, f)
    except IOError:
      print >> sys.stderr, "LOG: Image not found %s %s" % (os.path.basename(moduleDir), f)
  # If the dbk file has already been generated, include it
  dbkPath = os.path.join(moduleDir, 'index.included.dbk')
  if os.path.exists(dbkPath):
    dbkStr = open(dbkPath).read()
    files['index.included.dbk'] = dbkStr
  return (cnxml, files)

def convert(p, dbk1, files, collection_dir, output_xhtml):
  """ Converts a Docbook Element and a dictionary of files into a xhtml. """
  
  def transform(xslDoc, xmlDoc):
    """ Performs an XSLT transform and parses the <xsl:message /> text """
    ret = xslDoc(xmlDoc) # xslDoc(xmlDoc, **({'cnx.tempdir.path':"'%s'" % temp_dir}))
    for entry in xslDoc.error_log:
      # TODO: Log the errors (and convert JSON to python) instead of just printing
      print >> sys.stderr, entry.message.encode('utf-8')
    return ret

  def transformopf(xslDoc, xmlDoc,colpath):
    """ Performs an XSLT transform (SPECIFICALLY FOR OPF)and parses the <xsl:message /> text """
    ret = xslDoc(xmlDoc,opfpath="'%s'" % colpath) 
    for entry in xslDoc.error_log:
      print >> sys.stderr, entry.message.encode('utf-8')
    return ret

  # Step 1 (Cleaning up Docbook)
  p.start(2, 'Cleaning up Docbook')
  dbk2 = transform(DOCBOOK_CLEANUP_XSL, dbk1)

  # Step 2 (Docbook to XHTML)
  p.tick('Converting Docbook to XHTML')
  xhtml_file = os.path.join(os.getcwd(), output_xhtml)
  xhtml = transform(DOCBOOK2XHTML_XSL, dbk2)
  open(xhtml_file,'w').write(etree.tostring(xhtml))

  # Step 3 (Generate OPF file)
  colpath = os.path.abspath(collection_dir)+"/"#Pass the current working dir to xsl template to save opf file into that folder
  transformopf(DOCBOOK2OPF, dbk2, colpath)

  p.finish()

def main():

    try:
      import argparse
    except ImportError:
      print "argparse is needed for commandline"
      return 2

    parser = argparse.ArgumentParser(description='Convert an unzipped Collection to a .xhtml')
    parser.add_argument('-d', dest='collection_dir', help='Path to an unzipped collection', required=True)
    parser.add_argument('-o', dest='output_xhtml', help='Path to write the xhtml file', nargs='?', type=argparse.FileType('w'), default=sys.stdout)
    parser.add_argument('-r', dest='reduce_quality', help='Reduce image quality', action='store_true')
    args = parser.parse_args()

    # Verify the user pointed to a valid collection dir
    if not os.path.isdir(args.collection_dir) or not os.path.isfile(os.path.join(args.collection_dir, 'collection.xml')):
      print >> sys.stderr, "Must point to a valid collection directory (with a collection.xml file)"

     # Set the output file
    if args.output_xhtml == sys.stdout:
      output_xhtml = '/dev/stdout'
    else:
      output_xhtml = os.path.abspath(args.output_xhtml.name)

    stdErr = collection2mobi(args.collection_dir, output_xhtml, args.reduce_quality)

if __name__ == '__main__':
    sys.exit(main())
