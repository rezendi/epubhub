from google.appengine.api import memcache, urlfetch
import json, logging, urllib, zipfile, StringIO

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
        #logging.info("Rendering for root "+str(root)+" destination "+destination+" rendered "+str(rendered))

        raw = memcache.get(destination)
        if raw is None:
            url = 'http://wiki-sherpa.appspot.com/api/1/page'+destination+'?apiKey='+apiKey
            logging.info("Fetching "+url)
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
        html = '<?xml version="1.0" encoding="utf-8"?>\n'
        html+= '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">\n'
        html+= "<html><head><title>%s</title></head><body>%s</body></html>" % (name,body)
        images = top["images"] if "images" in top else []
        pages = [{ "title" : name , "uri" : top["url"], "contents" : html, "images" : images}]

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
        for idx, page in enumerate(pages):
            file.writestr(self.getFullPathFor(page,idx), page["contents"].encode("utf8"))
            for jdx, image in enumerate(page["images"]):
                file.writestr("OEBPS/Text/"+self.getImagePageFileNameFor(image,idx,jdx), self.getImagePageFor(image))
                raw = memcache.get(image["url"])
                if raw is None:
                    logging.info("Fetching "+image["url"])
                    response = urlfetch.fetch(image["url"])
                    raw = response.content
                file.writestr("OEBPS/Images/"+self.getImageFileNameFor(image), raw)
        file.close()
        logging.info("Zipped "+str(file.namelist()))
        return [file, stream]

    def getFullPathFor(self, page, idx):
        return "OEBPS/"+self.getPathFor(page, idx)

    def getPathFor(self, page, idx):
        return "Text/"+str(1000+idx)+"-0-"+self.getTitleFor(page)+".xhtml"
    
    def getTitleFor(self, page):
        title = page["title"].replace("/","_").replace(" ","_")
        return unicode(title)

    def getImageFileNameFor(self, image):
        filename = image["url"]
        slash = filename.rfind("/")
        filename = filename if slash<0 else filename[1+slash:]
        return filename
    
    def getImageNameFor(self, image):
        filename = image["name"]
        colon = filename.find(":")
        filename = filename if colon<0 else filename[1+colon:]
        filename = filename.strip().replace(" ","_")
        dot = filename.rfind(".")
        filename = filename if dot<0 else filename[:dot]
        return filename

    def getImagePageFileNameFor(self, image, idx, jdx):
        filename = self.getImageNameFor(image)
        return str(1000+idx)+"-"+str(1000+jdx)+"-"+filename+".xhtml"
    
    def getImagePageFor(self, image):
        tag = "<img src='../Images/"+self.getImageFileNameFor(image)+"' />"
        html = '<?xml version="1.0" encoding="utf-8"?>\n'
        html+= '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">'
        html+= "<html><head><title>%s</title></head><body>\n%s\n<HR/>%s\n</body></html>" % (image["name"], tag, image["name"])
        return unicode(html).encode("utf8")

    def getContainerXML(self):
        xml = '<?xml version="1.0" encoding="UTF-8" ?>'
        xml+= '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
        xml+= '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>'
        xml+= '</container>'
        return xml
    
    def getContentOBFFor(self, pages):
        book_uri = pages[0]["uri"]
        book_title = pages[0]["title"]
        xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
        xml+= '<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="2.0">\n'
        xml+= '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">\n'
        xml+= '<dc:title>%s</dc:title>\n' % book_title
        xml+= '<dc:language>en</dc:language>\n'
        xml+= '<dc:identifier id="BookId" opf:scheme="URI">%s</dc:identifier>\n' % book_uri
        xml+= '<dc:creator opf:file-as="WikiSherpa" opf:role="aut">WikiSherpa</dc:creator>\n'
        xml+= '<dc:publisher>Jedisaber.com</dc:publisher>'
        xml+= '</metadata>\n'
 
        xml+= '<manifest>\n'
        xml+= '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>\n'
        for idx, page in enumerate(pages):
            xml+= '<item id="%s" href="%s" media-type="application/xhtml+xml"/>\n' % (self.getTitleFor(page), self.getPathFor(page,idx))
#<item id="stylesheet" href="style.css" media-type="text/css"/>
#<item id="myfont" href="css/myfont.otf" media-type="application/x-font-opentype"/>
            for jdx, image in enumerate(page["images"]):
                filename = self.getImagePageFileNameFor(image,idx,jdx)
                xml+= '<item id="page_%s" href="%s" media-type="application/xhtml+xml"/>\n' % (self.getImageNameFor(image), "Text/"+filename)
                filename = self.getImageFileNameFor(image)
                mimetype = 'image/png' if filename.find('.png')>0 else 'image/jpeg'
                xml+= '<item id="image_%s" href="%s" media-type="%s"/>\n' % (self.getImageNameFor(image), "Images/"+filename, mimetype)
        xml+= '</manifest>\n'
        
        xml+= '<spine toc="ncx">\n'
        for idx, page in enumerate(pages):
            xml+= '<itemref idref="%s" />' % self.getTitleFor(page)
            for jdx, image in enumerate(page["images"]):
                xml+= '<itemref idref="page_%s" />\n' % self.getImageNameFor(image)
        xml+= '</spine>\n'
 
        xml+= '</package>'
        return unicode(xml).encode("utf8")

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
        xml+= '</head>\n'
        xml+= '<docTitle><text>%s</text></docTitle>' % book_title
        xml+= '<docAuthor><text>WikiSherpa</text></docAuthor>\n'
        xml+= '<navMap>\n'
        
        i = 1
        for idx, page in enumerate(pages):
            xml+= '<navPoint class="chapter" id="%s" playOrder="%s">' % (self.getTitleFor(page), str(i))
            xml+= '<navLabel><text>%s</text></navLabel>' % page["title"]
            xml+= '<content src="%s"/>' % self.getPathFor(page, idx)
            xml+= '</navPoint>\n'
            i+=1
            for jdx, image in enumerate(page["images"]):
                filename = self.getImagePageFileNameFor(image,idx,jdx)
                xml+= '<navPoint class="chapter" id="%s" playOrder="%s">' % (filename, str(i))
                xml+= '<navLabel><text>%s</text></navLabel>' % image["name"]
                xml+= '<content src="Text/'+filename+'"/>'
                xml+= '</navPoint>\n'
                i+=1

        xml+= '\n</navMap>'
        xml+= '</ncx>'
        return unicode(xml).encode("utf8")
