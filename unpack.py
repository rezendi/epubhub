import logging, zipfile
from HTMLParser import HTMLParser, HTMLParseError
from google.appengine.ext import blobstore, db
import model

class Unpacker:
    def unpack(self, key, zippedfile):
        ePubFile = db.get(key)
        existing = model.InternalFile.all().filter("epub = ", ePubFile)
        db.delete(existing)
        for filename in zippedfile.namelist():
            file = zippedfile.read(filename)
            data = None
            try:
              text = db.Text(file, encoding="utf-8")
            except Exception, ex:
              data = db.Blob(file)

            internalFile = model.InternalFile(
                epub = ePubFile,
                name = filename,
                text = text,
                data = data
            ).put()
            
            if filename.endswith("content.opf"):
                self.parseMetadata(ePubFile, file)

    def parseMetadata(self, ePubFile, content):
      parser = ePubMetadataParser()
      try:
        parser.feed(content)
        parser.close()
        ePubFile.creator = parser.results["creator"]
        ePubFile.title = parser.results["title"]
        ePubFile.publisher = parser.results["publisher"]
        ePubFile.language = parser.results["language"]
        ePubFile.put()
      except HTMLParseError, reason:
        logging.warn("HTML Parse Error from "+searchUrl+": "+str(reason))

class ePubMetadataParser(HTMLParser):
    def __init__(self):
      HTMLParser.__init__(self)
      self.currentText=''
      self.results=dict()

    def handle_starttag(self, tag, attrs):
        pass

    def handle_data(self, text):
        self.currentText=text

    def handle_endtag(self, tag):
        if tag=='dc:creator':
            self.results["creator"]=self.currentText
        if tag=='dc:title':
            self.results["title"]=self.currentText
        if tag=='dc:publisher':
            self.results["publisher"]=self.currentText
        if tag=='dc:language':
            self.results["language"]=self.currentText


