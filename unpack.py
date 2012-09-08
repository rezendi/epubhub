import logging, zipfile
from HTMLParser import HTMLParser, HTMLParseError
from google.appengine.api import search
from google.appengine.ext import blobstore, db
import model

class Unpacker:
    def unpack(self, epub):
        zippedfile = zipfile.ZipFile(blobstore.BlobReader(epub.blob.key()))
        existing = model.InternalFile.all().filter("epub = ", epub)
        db.delete(existing)
        replaceWith = None
        for filename in zippedfile.namelist():
            manifest = zippedfile.read(filename)
            if filename.endswith("content.opf"):
                possible_blobs = blobstore.BlobInfo.all().filter("size = ", epub.blob.size).fetch(10)
                for possible_blob in possible_blobs:
                    possible_epub = model.ePubFile.all().filter("blob_key = ", str(possible_blob.key())).get()
                    if possible_epub is not None:
                        internals = model.InternalFile.all().filter("epub = ", possible_epub)
                        for internal in internals:
                            if internal.path.endswith("content.opf") and internal.text==db.Text(manifest, encoding="utf-8"):
                                replaceWith = possible_epub
            
                #Deduplicate
                if replaceWith is None:
                    self.parseMetadata(epub, manifest)
                else:
                    entry = model.LibraryEntry.all().filter("epub = ", epub).get()
                    if entry is not None:
                        entry.epub = replaceWith
                        entry.put()
                        db.delete(epub)
                        return

        for filename in zippedfile.namelist():
            logging.info("Unpacking "+filename)
            file = zippedfile.read(filename)
            data = None
            try:
                text = db.Text(file, encoding="utf-8")
            except Exception, ex:
                data = db.Blob(file)

            internalFile = model.InternalFile(
                epub = epub,
                path = filename,
                text = text,
                data = data
            )
            internalFile.put()
            
    def parseMetadata(self, ePubFile, content):
      parser = ePubMetadataParser()
      try:
        parser.feed(content)
        parser.close()
        ePubFile.creator = parser.results["creator"] if parser.results.has_key("creator") else None
        ePubFile.title = parser.results["title"] if parser.results.has_key("title") else None
        ePubFile.publisher = parser.results["publisher"] if parser.results.has_key("publisher") else None
        ePubFile.language = parser.results["language"] if parser.results.has_key("language") else None
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


class Renderer:
    def contentHeader(self, internal):
        if internal.data is not None:
            return "image"
        path = internal.path
        if path.endswith(".css") or path.endswith(".txt") or path.endswith("mimetype"):
            return "text/plain"
        elif path.endswith(".xml") or path.endswith(".ncx") or path.endswith(".opf"):
            return "application/xml"
        return "text/html"

    def content(self, internal):
        if internal.data is not None:
            return internal.data
        
        text = internal.text
        sHead = text.find("</head>")
        if sHead == -1:
            sHead = text.find("</HEAD>")
        return text[:sHead]+self.overlay(internal)+text[sHead:]

    def overlay(self, internal):
        html = '<script src="/static/jquery-1.7.2.min.js"></script>\n'
        html+= '<script src="/static/ephubhost.js"></script>\n'
        html+= '<script>var epub="%s", file="%s"</script>\n' % (internal.epub.key(), internal.key())
        return html
      