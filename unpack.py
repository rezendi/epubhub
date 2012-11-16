import logging, urllib, traceback, xml.etree.ElementTree, zipfile
from google.appengine.api import search
from google.appengine.ext import blobstore, db
import model

class Unpacker:
    def unpack(self, epub):
        try:
            zippedfile = zipfile.ZipFile(blobstore.BlobReader(epub.blob))
            replaceWith = None
            mimetype = None
            toc = None

            for filename in zippedfile.namelist():
                if filename=="mimetype":
                    mimetype = zippedfile.read(filename)
                if filename.endswith(".opf"):
                    manifest = zippedfile.read(filename)
                    possible_blobs = blobstore.BlobInfo.all().filter("size = ", epub.blob.size).fetch(10)
                    for possible_blob in possible_blobs:
                        possible_epub = model.ePubFile.all().filter("blob = ", possible_blob.key()).get()
                        if possible_epub is not None:
                            for internal in possible_epub.internals():
                                if internal.path.endswith(".opf") and internal.text==db.Text(manifest, encoding="utf-8"):
                                    replaceWith = possible_epub
            
            if mimetype is None or mimetype.find("application/epub")==-1:
                raise Exception("Not an EPUB file")

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
            if filename.endswith(".opf"):
                toc = self.parseMetadata(epub, zippedfile.read(filename))

        for filename in sorted(filenames):
            if filename.endswith(".ncx"):
                toc = self.parseTOC(toc, epub, zippedfile.read(filename))

        for filename in model.sort_nicely(filenames):
            file = zippedfile.read(filename)
            isContentFile = filename.endswith("html") or filename.endswith("xml") and (file.find("<html")>0 or file.find("<HTML")>0)
            [text, data] = self.getTextOrData(file)
            order = -1

            if isContentFile:
                for key in toc.keys(): # O(n^2) but I think that's OK here
                    dict = toc[key]
                    tocName = dict["filename"].replace("%20"," ")
                    if filename.endswith(tocName):
                        name = dict["name"] if dict.has_key("name") else self.getNameFromFilename(filename)
                        order = dict["order"] if dict.has_key("order") else -1
                        logging.info("Unpacking content file %s" % filename)
            else:
                name = self.getNameFromFilename(filename)
                logging.info("Unpacking meta file %s " % filename)

            internalFile = model.InternalFile(
                epub = epub,
                path = filename,
                text = text,
                data = data,
                order = order,
                name = name
            )
            internalFile.put()
        
    def getTextOrData(self, file):
        try:
            text = db.Text(file, encoding="utf-8")
            return [text, None]
        except Exception, ex:
            order = 0
            data = db.Blob(file)
            return [None, data]

    def getNameFromFilename(self, filename):
        name = filename.rpartition("/")[2] if filename.find("/") else filename
        name = name.replace(".html","").replace(".htm","").replace(".xml","")
        name = name.rpartition(".")[0] if name.find(".")>0 else name
        name = "..." if len(name)==0 else name
        return name

    def parseMetadata(self, epub, content):
        try:
            logging.info("Parsing metadata")
            to_parse = unicode(content,"utf-8",errors="ignore")
            to_parse = to_parse.encode("utf-8")
            root = xml.etree.ElementTree.fromstring(to_parse)
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
                        if child.text is None:
                            epub.description = None
                        else:
                            description = child.text.replace("\n"," ")
                            description = description.replace("&nbsp;"," ").replace("&amp;","&")
                            description = description.replace("&gt;",">").replace("&lt;","<")
                            epub.description = db.Text(description)
                    if child.tag.find("date")>0:
                        epub.date = child.text
                except Exception, ex:
                    logging.error("Problem with metadata element %s: %s" % (child,ex))
            epub.put()
        
        except Exception, ex:
            logging.error("Metadata error: %s" % ex)
            epub.creator = "Metadata error"

        toc = {}
        manifest = root.find(ns+"manifest")
        for child in manifest:
            id = child.attrib["id"]
            toc[id] = {}
            toc[id]["filename"] = child.attrib["href"]

        spine = root.find(ns+"spine")
        i=0
        for child in spine:
            idref = child.attrib["idref"]
            toc[idref]["order"] = i
            i+=1
        
        #logging.info("Got toc %s" % toc)
        return toc

    def parseTOC(self, toc, epub, content):
        to_parse = unicode(content,"utf-8",errors="ignore")
        to_parse = to_parse.encode("utf-8")
        root = xml.etree.ElementTree.fromstring(to_parse)
        ns = root.tag[:root.tag.rfind("}")+1] if root.tag.find("{")==0 else root.tag
        title = root.find(ns+"docTitle").find(ns+"text").text
        if title is not None:
            epub.title = title
            epub.put()
            
        for navPoint in root.iter(ns+"navPoint"):
            name = navPoint.find(ns+"navLabel").find(ns+"text").text
            path = navPoint.find(ns+"content").attrib["src"]
            order = navPoint.attrib["playOrder"]
            if path is None:
                continue
            for key in toc.keys(): # O(n^2) but I think that's OK here
                dict = toc[key]
                if dict["filename"].endswith(path) and name is not None:
                    dict["name"] = name
                    #dict["order"] = int(order) if order is not None else dict["order"]
                
        return toc

    def index_epub(self, epub, index_name, user=None):
        index = search.Index(index_name)
        for internal in epub.internals():
            if internal.isContentFile():
                logging.info("Indexing "+internal.path)
                internal_id = str(internal.key())
                existing = index.list_documents(internal_id, limit=1)
                for document in existing:
                    if document.doc_id == internal_id:
                        for field in document.fields:
                            if field.name=="owners" and field.value is not None and field.value.find(user)==-1:
                                user = field.value if user is None else +"|\n|"+user
                document = search.Document(
                    doc_id=internal_id,
                    fields=[
                        search.TextField(name="owners", value="public" if user is None else user),
                        search.TextField(name="book", value=str(epub.key())),
                        search.TextField(name="name", value=internal.name),
                        search.HtmlField(name="html", value=internal.text)
                    ]
                )
                index.add(document)

    def index_quote(self, quote):
        index = search.Index("quotes")
        document = search.Document(
            doc_id=str(quote.key()),
            fields=[
                search.TextField(name="user",value=str(quote.user.key())),
                search.TextField(name="book",value=str(quote.epub.key())),
                search.TextField(name="file",value=str(quote.file.key())),
                search.HtmlField(name="html",value=quote.html)
            ]
        )
        index.add(document)
        
    def contentHeader(self, internal):
        if internal.data is not None:
            return "image"
        if internal.isContentFile():
            return "text/html"
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
        
        if not internal.isContentFile():
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
        next_file = epub.internals().filter("order =",selected.order+2).get() if next_file is None else next_file
        next = next_file.path if next_file is not None else None
        prev_file = epub.internals().filter("order =",selected.order-1).get()
        prev_file = epub.internals().filter("order =",selected.order-2).get() if prev_file is None else prev_file
        prev = prev_file.path if prev_file is not None else None
        
        html+= '<script>var epub_share="true", epub_title="%s", epub_chapter="%s", epub_total="%s", epub_id="%s", epub_internal="%s", epub_next="%s", epub_prev="%s"</script>\n' % (epub.title, selected.order, total, epub.key().id(), selected.key(), next, prev)
        return html
    