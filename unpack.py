import logging, zipfile
from HTMLParser import HTMLParser, HTMLParseError
from google.appengine.api import search
from google.appengine.ext import blobstore, db
import model

class Unpacker:
    def unpack(self, key, zippedfile):
        ePubFile = db.get(key)
        existing = model.InternalFile.all().filter("epub = ", ePubFile)
        db.delete(existing)
        for filename in zippedfile.namelist():
            logging.info("Unpacking "+filename)
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
            )
            internalFile.put()
            
            if filename.endswith("html"):
                document = search.Document(
                    doc_id=str(internalFile.key()),
                    fields=[search.HtmlField(name="content",value=text)]
                )
                search.Index(name="chapters").add(document)
            if filename.endswith("content.opf"):
                self.parseMetadata(ePubFile, file)

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
        path = internal.name
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
        return text[:sHead]+self.overlay()+text[sHead:]

    def overlay(self):
        html = '<script type="text/javascript" src="http://code.jquery.com/jquery-1.7.2.min.js"></script>\n'
        html+= '<script type="text/javascript">\n'
        html+= '/*<![CDATA[*/\n'
        html+= '$("p").hover(function() { $(this).css("background-color","red;"); });\n'
        html+= '$("p").click(function() { $(this).hide(); });\n'
        html+= '$("#necronomicon").click(function() { $(this).hide(); });\n'
        html+= '/*]]>*/\n'
        html+= '</script>\n'
        return html