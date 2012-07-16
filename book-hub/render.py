from google.appengine.api import memcache, urlfetch
import logging, json, zipfile, StringIO

class Renderer:
    def renderPage(self, destination, rendered = [], root = None):
        apiKey = 'e564b390-ceb5-11e1-9b23-0800200c9a66'
        destination = destination.strip()
        destination = destination.replace(" ","_").replace("%20","_")
        if not destination.startswith('/'):
            destination = '/en/'+destination
        if destination in rendered:
            return
        rendered.append(destination)
        logging.info("Rendering for root "+str(root)+" destination "+destination+" rendered "+str(rendered))

        raw = memcache.get(destination)
        if raw is None:
            url = 'http://wiki-sherpa.appspot.com/api/1/page'+destination+'?apiKey='+apiKey
            response = urlfetch.fetch(url)
            raw = unicode(response.content)

        try:
            top = json.loads(raw)
        except Exception, reason:
            logging.warning("Could not parase JSON", reason)
            return None

        memcache.add(destination, raw)

        name = top["name"]
        if root is None:
            root = "/"+top["locale"]+"/"+top["name"].replace(" ","_")
        body = self.renderSection(top)
        rendered.append(name)
        html = "<html><head><title>%s</title></head><body>%s</body></html>" % (name,body)
        pages = [{ "title" : name , "uri" : top["url"], "contents" : html}]

        if "subpages" in top:
            if not root in top["subpages"]:
                for subpage in top["subpages"]:
                    subpages = self.renderPage(subpage, rendered, root)
                    if subpages is not None:
                        pages.extend(subpages)

        return pages

    def renderSection(self, section, rank=1):
        html ="<H"+str(rank)+">"+section["name"]+"</H"+str(rank)+">"
        if "text" in section:
            html+=section["text"]
        if "sections" in section:
            for subsection in section["sections"]:
                html += self.renderSection(subsection, rank+1)
        if "listings" in section:
            for listing in section["listings"]:
                html+="<HR/>"+unicode(json.dumps(listing))
        html+="<HR/>"
        return html

class Zipper:
    def zipPages(self, pages):
        stream = StringIO.StringIO()
        file = zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED, False)
        file.writestr("mimetype", "application/epub+zip")
        file.writestr("META-INF/container.xml", self.getContainerXML())
        file.writestr("OEBPS/content.opf", self.getContentOBFFor(pages))
        file.writestr("OEBPS/toc.ncx", self.getTOCFor(pages))
        for page in pages:
            file.writestr(self.getFullPathFor(page), page["contents"].encode("utf8"))
        file.close()
        logging.info("Zipped "+str(file.namelist()))
        return [file, stream]

    def getFullPathFor(self, page):
        return "OEBPS/"+self.getPathFor(page)

    def getPathFor(self, page):
        return self.getTitleFor(page)+".xhtml"
    
    def getTitleFor(self, page):
        return page["title"].encode("utf8").replace("/","_").replace(" ","_")

    def getContainerXML(self):
        xml = '<?xml version="1.0" encoding="UTF-8" ?>'
        xml+= '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
        xml+= '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>'
        xml+= '</container>'
        return xml
    
    def getContentOBFFor(self, pages):
        book_uri = pages[0]["uri"]
        book_title = pages[0]["title"]
        xml = '<?xml version="1.0"?>'
        xml+= '<package version="2.0" xmlns="http://www.idpf.org/2007/opf" unique-identifier="%s">' % book_uri
        xml+= '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">'
        xml+= '<dc:title>%s</dc:title>' % book_title
        xml+= '<dc:language>en</dc:language>'
        xml+= '<dc:identifier id="BookId" opf:scheme="URI">%s</dc:identifier>' % book_uri
        xml+= '<dc:creator opf:file-as="WikiSherpa" opf:role="aut">WikiSherpa</dc:creator>'
        xml+= '</metadata>'
 
        xml+= '<manifest>'
        for page in pages:
            xml+= '<item id="%s" href="%s" media-type="application/xhtml+xml"/>' % (self.getTitleFor(page), self.getPathFor(page))
#<item id="stylesheet" href="style.css" media-type="text/css"/>
#<item id="ch1-pic" href="ch1-pic.png" media-type="image/png"/>
#<item id="myfont" href="css/myfont.otf" media-type="application/x-font-opentype"/>
        xml+= '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>'
        xml+= '</manifest>'
        
        xml+= '<spine toc="ncx">'
        for page in pages:
            xml+= '<itemref idref="%s" />' % self.getTitleFor(page)
        xml+= '</spine>'
 
        xml+= '</package>'
        return xml

    def getTOCFor(self, pages):
        book_uri = pages[0]["uri"]
        book_title = pages[0]["title"]
        xml = '<?xml version="1.0" encoding="UTF-8"?>'
        xml+= '<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN" "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">'
        xml+= '<ncx version="2005-1" xml:lang="en" xmlns="http://www.daisy.org/z3986/2005/ncx/">'
        xml+= '<head>'
        xml+= '<meta name="dtb:uid" content="%s"/>' % book_uri
        xml+= '<meta name="dtb:depth" content="1"/>'
        xml+= '<meta name="dtb:totalPageCount" content="0"/>'
        xml+= '<meta name="dtb:maxPageNumber" content="0"/>'
        xml+= '</head>'
        xml+= '<docTitle><text>%s</text></docTitle>' % book_title
        xml+= '<docAuthor><text>WikiSherpa</text></docAuthor>'
        xml+= '<navMap>'
        
        i = 1
        for page in pages:
            xml+= '<navPoint class="chapter" id="%s" playOrder="%s">' % (self.getTitleFor(page), str(i))
            xml+= '<navLabel><text>%s</text></navLabel>' % page["title"]
            xml+= '<content src="%s"/>' % self.getPathFor(page)
            xml+= '</navPoint>'
            i+=1

        xml+= '</navMap>'
        xml+= '</ncx>'
        return xml
