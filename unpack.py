import logging, urllib, xml.etree.ElementTree, zipfile
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
        try:
            root = xml.etree.ElementTree.fromstring(content.encode("utf-8"))
            ns = root.tag[:root.tag.rfind("}")+1] if root.tag.find("{")==0 else root.tag
            metadata = root.find(ns+"metadata")
            for child in metadata:
                if child.tag.find("creator")>0:
                    ePubFile.creator = child.text
                if child.tag.find("title")>0:
                    ePubFile.title = child.text
                if child.tag.find("publisher")>0:
                    ePubFile.publisher = child.text
                if child.tag.find("language")>0:
                    ePubFile.language = child.text
            ePubFile.put()
        except Exception, ex:
            logging.error("Metadata error: %s" % ex)
            epubFile.creator = "Metadata error"
        
    def getTOC(self, file):
        internals = model.InternalFile.all().filter("epub = ",file)
        points = []
        for internal in internals:
            if internal.path.endswith("toc.ncx"):
                root = xml.etree.ElementTree.fromstring(internal.text.encode("utf-8"))
                ns = root.tag[:root.tag.rfind("}")+1] if root.tag.find("{")==0 else root.tag
                #ns = root.tag.replace("}ncx","}")
                title = root.find(ns+"docTitle").find(ns+"text").text
                for navPoint in root.iter(ns+"navPoint"):
                    points.append({"name" : navPoint.find(ns+"navLabel").find(ns+"text").text, "path" : navPoint.find(ns+"content").attrib["src"]})
                for point in points:
                    if point["path"].find("OEBPS")<0:
                        point["path"]="OEBPS/"+point["path"]
                return title, points
        for internal in internals:
            points.append({"name" : None, "path" : internal.path})
        return internal.epub.title, points
    
    def getNextPrevLinks(self, internal):
        epub = internal.epub
        title, points = self.getTOC(epub)
        prev,next,chapter = "","",0
        for idx, point in enumerate(points):
            if internal.path.endswith(urllib.unquote_plus(point["path"])):
                chapter = idx+1
                prev = points[idx-1]["path"] if idx > 0 else ""
                next = points[idx+1]["path"] if idx+1 < len(points) else ""
        return chapter, len(points), prev, next

    def contentHeader(self, internal):
        if internal.data is not None:
            return "image"
        path = internal.path
        if path.endswith(".css"):
            return "text/css"
        if path.endswith(".txt") or path.endswith("mimetype"):
            return "text/plain"
        elif path.endswith(".xml") or path.endswith(".ncx") or path.endswith(".opf"):
            return "application/xml"
        return "text/html"

    def content(self, internal):
        if internal.data is not None:
            return internal.data
        
        if not internal.path.endswith("html"):
            return internal.text

        text = internal.text
        sHead = text.find("</HEAD>") if text.find("</head>")==-1 else text.find("</head>")
        return text[:sHead]+self.overlay(internal)+text[sHead:]

    def overlay(self, internal):
        html = '<script src="/static/jquery-1.7.2.min.js"></script>\n'
        html+= '<script src="/static/ephubhost.js"></script>\n'
        chapter,total,prev,next = self.getNextPrevLinks(internal)
        html+= '<script>var epub_share="true", epub_title="%s", epub_chapter="%s", epub_total="%s", epub_file="%s", epub_internal="%s", epub_next="%s", epub_prev="%s"</script>\n' % (internal.epub.title, chapter, total, internal.epub.key(), internal.key(), next, prev)
        return html
    