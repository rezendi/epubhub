import logging, urllib, traceback, xml.etree.ElementTree, zipfile
from google.appengine.api import search
from google.appengine.ext import blobstore, db
import model

class Unpacker:
    def unpack(self, epub):
        try:
            zippedfile = zipfile.ZipFile(blobstore.BlobReader(epub.blob))
            replaceWith = None
            toc = None
            for filename in zippedfile.namelist():
                if filename.endswith("content.opf"):
                    manifest = zippedfile.read(filename)
                    possible_blobs = blobstore.BlobInfo.all().filter("size = ", epub.blob.size).fetch(10)
                    for possible_blob in possible_blobs:
                        possible_epub = model.ePubFile.all().filter("blob = ", possible_blob.key()).get()
                        if possible_epub is not None:
                            for internal in possible_epub.internals():
                                if internal.path.endswith("content.opf") and internal.text==db.Text(manifest, encoding="utf-8"):
                                    replaceWith = possible_epub
            
            if replaceWith is None:
                self.unpack_internal(epub)
                return None, None
            else: #duplicate entry found
                logging.info("Duplicate entry found")
                entry = model.LibraryEntry.all().filter("epub = ", epub).get()
                if entry is not None:
                    entry.epub = replaceWith
                    entry.put()
                    blobstore.delete(epub.blob.key())
                    db.delete(epub)
                return replaceWith, None

        except Exception, ex:
            logging.error("Unexpected error: %s" % traceback.format_exc(ex))
            error = "Unable to unpack epub %s due to %s" % (epub, ex)
            return None, error

    def unpack_internal(self, epub):
        zippedfile = zipfile.ZipFile(blobstore.BlobReader(epub.blob.key()))
        db.delete(epub.internals())
        toc = None
        filenames = []
        for filename in zippedfile.namelist():
            filenames.append(filename)
        
        for filename in sorted(filenames):
            if filename.endswith("content.opf"):
                self.parseMetadata(epub, zippedfile.read(filename))
            if filename.endswith("toc.ncx"):
                toc_text = db.Text(zippedfile.read(filename), encoding="utf-8")
                toc = self.getTOCFrom(toc_text)

        index = 0
        internalFiles = []
        for filename in sorted(filenames):
            if filename.endswith("html"):
                index+=1
            logging.info("Unpacking "+filename)
            file = zippedfile.read(filename)
            name = filename.rpartition("/")[2]
            name = name.replace(".html","")
            name = name.replace(".htm","")
            name = name.rpartition(".")[0] if name.rfind(".")>0 else name
            name = "..." if len(name)==0 else name
            data = None
            try:
                text = db.Text(file, encoding="utf-8")
                order = index if filename.endswith("html") else 0
                if toc is not None:
                    order = index if filename.endswith("html") else 0
                    for point in toc["points"]:
                        path = urllib.unquote_plus(point["path"])
                        if filename.endswith(path):
                            if point["name"] is not None and len(point["name"])>0:
                                name = point["name"]
                            order = int(point["order"]) if int(point["order"])>0 else index
            except Exception, ex:
                order = 0
                data = db.Blob(file)

            internalFile = model.InternalFile(
                epub = epub,
                path = filename,
                text = text,
                data = data,
                order = order,
                name = name
            )
            internalFiles.append(internalFile)
        
        logging.info("Ordering %s files" % len(internalFiles))
        count = 0
        for internal in sorted(internalFiles, key = lambda file:file.order):
            if internal.order > 0:
                count+=1
                internal.order = count
            internal.put()
        logging.info("Ordered %s content files" % count)
            
    def parseMetadata(self, epub, content):
        try:
            root = xml.etree.ElementTree.fromstring(content.encode("utf-8"))
            ns = root.tag[:root.tag.rfind("}")+1] if root.tag.find("{")==0 else root.tag
            metadata = root.find(ns+"metadata")
            for child in metadata:
                try:
                    if child.tag.find("language")>0:
                        epub.language = child.text
                    if child.tag.find("title")>0:
                        epub.title = child.text
                    if child.tag.find("creator")>0:
                        epub.creator = child.text
                    if child.tag.find("publisher")>0:
                        epub.publisher = child.text
                    if child.tag.find("rights")>0:
                        epub.rights = child.text
                    if child.tag.find("contributor")>0:
                        epub.contributor = child.text
                    if child.tag.find("identifier")>0:
                        epub.identifier = child.text
                    if child.tag.find("description")>0:
                        epub.description = child.text
                    if child.tag.find("date")>0:
                        epub.date = child.text
                except Exception, ex:
                    logging.error("Problem with metadata element %s: %s" % (child,ex))
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
    
    def index(self, epub, user, index_name):
        index = search.Index(index_name)
        for internal in epub.internals():
            if internal.path.endswith("html"):
                logging.info("Indexing "+internal.path)
                internal_id = str(internal.key())
                existing = index.list_documents(internal_id, limit=1)
                for document in existing:
                    if document.doc_id == internal_id:
                        for field in document.fields:
                            if field.name=="owners" and field.value is not None and field.value.find(user)==-1:
                                user=field.value+"|\n|"+user
                document = search.Document(
                    doc_id=internal_id,
                    fields=[
                        search.TextField(name="owners",value=user),
                        search.TextField(name="book",value=str(epub.key())),
                        search.TextField(name="name",value=internal.name),
                        search.HtmlField(name="html",value=internal.text)
                    ]
                )
                index.add(document)


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
        elif path.endswith(".json"):
            return "application/json"
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
        html = '<link type="text/css" rel="stylesheet" href="/static/epubhost.css" />\n'
        html+= '<script src="/static/jquery-1.7.2.min.js"></script>\n'
        html+= '<script src="/static/epubhost.js"></script>\n'
        epub = selected.epub
        total = epub.internals(only_chapters=True).count()

        next_file = epub.internals().filter("order =",selected.order+1).get()
        next = next_file.path if next_file is not None else None
        prev_file = epub.internals().filter("order =",selected.order-1).get()
        prev = prev_file.path if prev_file is not None else None
        
        html+= '<script>var epub_share="true", epub_title="%s", epub_chapter="%s", epub_total="%s", epub_file="%s", epub_internal="%s", epub_next="%s", epub_prev="%s"</script>\n' % (epub.title, selected.order, total, epub.key(), selected.key(), next, prev)
        return html
    