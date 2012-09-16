import logging, urllib, xml.etree.ElementTree, zipfile
from google.appengine.api import search
from google.appengine.ext import blobstore, db
import model

class Unpacker:
    def unpack(self, epub):
        zippedfile = zipfile.ZipFile(blobstore.BlobReader(epub.blob.key()))
        replaceWith = None
        toc = None
        for filename in zippedfile.namelist():
            thisfile = zippedfile.read(filename)
            if filename.endswith("content.opf"):
                manifest = thisfile
                possible_blobs = blobstore.BlobInfo.all().filter("size = ", epub.blob.size).fetch(10)
                for possible_blob in possible_blobs:
                    possible_epub = model.ePubFile.all().filter("blob_key = ", str(possible_blob.key())).get()
                    if possible_epub is not None:
                        for internal in possible_epub.internals():
                            if internal.path.endswith("content.opf") and internal.text==db.Text(manifest, encoding="utf-8"):
                                replaceWith = possible_epub
            
                #Deduplicate
                if replaceWith is None:
                    self.parseMetadata(epub, manifest)
                    self.unpack_internal(epub)
                else:
                    entry = model.LibraryEntry.all().filter("epub = ", epub).get()
                    if entry is not None:
                        entry.epub = replaceWith
                        entry.put()
                        db.delete(epub)
                        return

    def unpack_internal(self, epub):
        zippedfile = zipfile.ZipFile(blobstore.BlobReader(epub.blob.key()))
        db.delete(epub.internals())
        for filename in zippedfile.namelist():
            if filename.endswith("toc.ncx"):
                toc_text = db.Text(zippedfile.read(filename), encoding="utf-8")
                toc = self.getTOCFrom(toc_text)

        for idx, filename in enumerate(zippedfile.namelist()):
            logging.info("Unpacking "+filename)
            file = zippedfile.read(filename)
            name = filename.rpartition("/")[2]
            data = None
            try:
                text = db.Text(file, encoding="utf-8")
                if toc is None:
                    order = idx
                else:
                    order = 0
                    for point in toc["points"]:
                        path = urllib.unquote_plus(point["path"])
                        if filename.endswith(path):
                            if point["name"] is not None and len(point["name"])>0:
                                name = point["name"]
                            order = int(point["order"])
            except Exception, ex:
                data = db.Blob(file)

            #logging.info("setting order to %s for %s" % (order, name))
            internalFile = model.InternalFile(
                epub = epub,
                path = filename,
                text = text,
                data = data,
                order = order,
                name = name
            )
            internalFile.put()
            
    def parseMetadata(self, epub, content):
        try:
            root = xml.etree.ElementTree.fromstring(content.encode("utf-8"))
            ns = root.tag[:root.tag.rfind("}")+1] if root.tag.find("{")==0 else root.tag
            metadata = root.find(ns+"metadata")
            for child in metadata:
                if child.tag.find("creator")>0:
                    epub.creator = child.text
                if child.tag.find("title")>0:
                    epub.title = child.text
                if child.tag.find("publisher")>0:
                    epub.publisher = child.text
                if child.tag.find("language")>0:
                    epub.language = child.text
            epub.put()
        except Exception, ex:
            logging.error("Metadata error: %s" % ex)
            epub.creator = "Metadata error"
        
    def getTOCFrom(self, content):
        root = xml.etree.ElementTree.fromstring(content.encode("utf-8"))
        ns = root.tag[:root.tag.rfind("}")+1] if root.tag.find("{")==0 else root.tag
        title = root.find(ns+"docTitle").find(ns+"text").text
        points = []
        for navPoint in root.iter(ns+"navPoint"):
            points.append({"name" : navPoint.find(ns+"navLabel").find(ns+"text").text,
                           "path" : navPoint.find(ns+"content").attrib["src"],
                           "order" : navPoint.attrib["playOrder"]
                           })
        return {"title" : title, "points" :points}
    
    def getNextPrevLinks(self, selected):
        chapter = 0
        count = 0
        prev = ""
        next = ""
        for idx,internal in enumerate():
            count+=1
            if internal==selected:
                chapter = idx+1
                prev = points[idx-1].path if idx > 0 else ""
                next = points[idx+1].path if idx+1 < len(points) else ""
        return chapter, count, prev, next

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

    def overlay(self, selected):
        html = '<script src="/static/jquery-1.7.2.min.js"></script>\n'
        html+= '<script src="/static/ephubhost.js"></script>\n'
        epub = selected.epub
        total = epub.internals(only_chapters=True).count()
        next_file = None if selected.order==total else epub.internals().filter("order =",selected.order+1).get()
        next = next_file.path if next_file is not None else None
        prev_file = None if selected.order==0 else epub.internals().filter("order =",selected.order-1).get()
        prev = prev_file.path if prev_file is not None else None
        html+= '<script>var epub_share="true", epub_title="%s", epub_chapter="%s", epub_total="%s", epub_file="%s", epub_internal="%s", epub_next="%s", epub_prev="%s"</script>\n' % (epub.title, selected.order, total, epub.key(), selected.key(), next, prev)
        return html
    