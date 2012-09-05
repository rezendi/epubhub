from google.appengine.api import memcache, urlfetch
import json, logging, urllib, re, zipfile, StringIO

class Renderer:
    def renderPage(self, destination, rendered = [], root = None):
        apiKey = 'e564b390-ceb5-11e1-9b23-0800200c9a66'
        destination = destination.strip()
        destination = destination.replace(" ","_").replace("%20","_")
        if not destination.startswith('/'):
            destination = '/en/'+destination
        if destination in rendered:
            return []
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
            logging.warning("Could not parse JSON", reason)
            return []

        memcache.add(destination, raw)
        images = top["images"] if "images" in top else []

        name = top["name"]
        rendered.append(name)
        if root is None:
            root = "/"+top["locale"]+"/"+top["name"].replace(" ","_")
        
        wikipedia = None
        if "sections" in top:
            sections = top["sections"]
            last = sections[len(sections)-1]
            if "name" in last and last["name"]=="Wikipedia":
                wikipedia = sections.pop()

        html = '<?xml version="1.0" encoding="utf-8"?>\n'
        html+= '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">\n'

        if wikipedia is not None:
            body = self.renderSection(wikipedia)
            wikip_images = wikipedia["images"] if "images" in wikipedia else []
            self.collectImages(wikipedia, wikip_images)
            wikip_html = html+"<html><head><title>%s</title></head><body>%s</body></html>" % (name, body)
            wikip_page = { "title" : "Wikipedia" , "uri" : top["url"]+"/Wikipedia", "contents" : wikip_html, "images" : wikip_images}
            
        if len(raw)<65536 or not "sections" in top:
            body = self.renderSection(top)
            html+= "<html><head><title>%s</title></head><body>%s</body></html>" % (name, body)
            self.collectImages(top, images)
            pages = [] if len("body")>256 else [{ "title" : name , "uri" : top["url"], "contents" : html, "images" : images}]
        else:
            body = self.renderSection(top, cascade=False)
            page_html = html+"<html><head><title>%s</title></head><body>%s</body></html>" % (name, body)
            pages = [{ "title" : name , "uri" : top["url"], "contents" : page_html, "images" : images}]
            for section in top["sections"]:
                images = section["images"] if "images" in section else []
                self.collectImages(section, images)
                name = section["name"]
                body = self.renderSection(section)
                if len(body)==0:
                    continue
                page_html = html+"<html><head><title>%s</title></head><body>%s</body></html>" % (name, body)
                section_page = { "title" : name , "uri" : top["url"]+"/"+name, "contents" : page_html, "images" : images}
                pages.append(section_page)
        
        if wikipedia is not None:
            pages.append(wikip_page)

        if "subpages" in top:
            if not root in top["subpages"]:
                for subpage in top["subpages"]:
                    subpages = self.renderPage(subpage, rendered, root)
                    if subpages is not None:
                        pages.extend(subpages)

        return pages

    def renderSection(self, section, rank=1, cascade=True):
        html ="<a name=\""+section["name"]+"></a><H"+str(rank)+">"+section["name"]+"</H"+str(rank)+">"
        keep = False
        if "images" in section:
            keep = True
            for image in section["images"]:
                html+= "<div class='image' style='width:100%;'><center><img src='../Images/"+self.getImageFileNameFor(image)+"' />";
                html+= "<br/><i>"+self.getDisplayNameFor(image)+"</i></center></div>"
        if "text" in section and len(re.sub('<[^<]+?>', '', section["text"]))>16:
            keep = True
            html+=section["text"]
        if cascade and "sections" in section:
            keep = True
            for subsection in section["sections"]:
                html += self.renderSection(subsection, rank+1)
        if "listings" in section:
            keep = True
            for listing in section["listings"]:
                if not "name" in listing:
                    continue
                html+="<LI><b>%s</b>" % listing["name"]
                if "alt" in listing and len(listing["alt"].strip())>0:
                    html+=" (<i>%s</i>)" % listing["alt"]
                if "address" in listing and len(listing["address"].strip())>0:
                    html+=", <i>address:</i> %s" % listing["address"]
                if "directions" in listing and len(listing["directions"].strip())>0:
                    html+=" (<i>%s</i>)" % listing["directions"]
                if "email" in listing and len(listing["email"].strip())>0:
                    html+=", <i>email:</i> %s" % listing["email"]
                if "phone" in listing and len(listing["phone"].strip())>0:
                    html+=", <i>phone:</i> %s" % listing["phone"]
                if "fax" in listing and len(listing["fax"].strip())>0:
                    html+=", <i>fax:</i> %s" % listing["fax"]
                if "url" in listing and len(listing["url"].strip())>0:
                    html+=", <i>url:</i> <a href='%s'>%s</a>" % (listing["url"],listing["url"])
                if "hours" in listing and len(listing["hours"].strip())>0:
                    html+=", <i>hours:</i> %s" % listing["hours"]
                if "price" in listing and len(listing["price"].strip())>0:
                    html+=", <i>price:</i> %s" % listing["price"]
                if "checkin" in listing and len(listing["checkin"].strip())>0:
                    html+=", <i>check in:</i> %s" % listing["checkin"]
                if "checkout" in listing and len(listing["checkout"].strip())>0:
                    html+=", <i>check out:</i> %s" % listing["checkout"]
                html+=". "
                if "description" in listing and len(listing["description"].strip())>0:
                    html+=listing["description"]+"<br/>"
                else:
                    html+="<br/>"
                html+="<br/>"
        if not keep:
            return ""
        html+="<HR/>"
        return html
    
    def getDisplayNameFor(self, image):
        return image["name"].replace("Image: ","")

    def collectImages(self, section, images):
        if "images" in section:
            for image in section["images"]:
                if not image in images:
                    images.append(image)
        if "sections" in section:
            for subsection in section["sections"]:
                self.collectImages(subsection, images)

    def getImageFileNameFor(self, image):
        filename = image["url"] # image["secondUrl"] if "secondUrl" in image else image["url"]
        slash = filename.rfind("/")
        filename = filename if slash<0 else filename[1+slash:]
        filename = filename.strip().replace(" ","_").replace("'","").replace("%27","").replace("%28","").replace("%2C","")
        filename = filename.replace("!","").replace(",","")
        filename = filename.encode("ascii","ignore")
        return filename
    
class Zipper:
    def zipPages(self, pages):
        stream = StringIO.StringIO()
        file = zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED, False)
        file.writestr("mimetype", "application/epub+zip")
        file.writestr("META-INF/container.xml", self.getContainerXML())
        file.writestr("OEBPS/content.opf", self.getContentOBFFor(pages))
        file.writestr("OEBPS/toc.ncx", self.getTOCNCXFor(pages))
        file.writestr("OEBPS/Text/toc.html", self.getTOCHTMLFor(pages))
        imageurls = []
        for page in pages:
            file.writestr(self.getFullPathFor(page), page["contents"].encode("utf8"))
            for image in page["images"]:
                url = image["url"] # image["secondUrl"] if "secondUrl" in image else image["url"]
                if url not in imageurls:
                    raw = memcache.get(url)
                    if raw is None:
                        logging.info("Fetching "+url)
                        response = urlfetch.fetch(url)
                        raw = response.content
                    imageurls.append(url)
                    file.writestr("OEBPS/Images/"+self.getImageFileNameFor(image), raw)
        logging.info("Zipped "+str(file.namelist()))
        file.close()
        return [file, stream]

    def getFullPathFor(self, page):
        return "OEBPS/"+self.getPathFor(page)

    def getPathFor(self, page):
        path = "Text/"+self.getTitleFor(page)+".xhtml"
        return path.encode("ascii","ignore")

    def getTitleFor(self, page):
        title = page["title"].replace("/","_").replace(" ","_")
        return unicode(title)

    def getImageFileNameFor(self, image):
        filename = image["url"]
        slash = filename.rfind("/")
        filename = filename if slash<0 else filename[1+slash:]
        filename = filename.strip().replace(" ","_").replace("'","").replace("%27","").replace("%28","").replace("%2C","")
        filename = filename.replace("!","").replace(",","")
        filename = filename.encode("ascii","ignore")
        return filename
    
    def getImageNameFor(self, image):
        filename = image["name"]
        colon = filename.find(":")
        filename = filename if colon<0 else filename[1+colon:]
        filename = filename.strip().replace(" ","_").replace("'","").replace("%27","").replace("%28","").replace("%2C","")
        filename = filename.replace("!","").replace(",","")
        dot = filename.rfind(".")
        filename = filename if dot<0 else filename[:dot]
        return filename

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
        xml+= '<item id="toc" href="Text/toc.html" media-type="application/xhtml+xml"/>\n'
        ids = []
        for page in pages:
            xml+= '<item id="%s" href="%s" media-type="application/xhtml+xml"/>\n' % (self.getTitleFor(page), self.getPathFor(page))
#<item id="stylesheet" href="style.css" media-type="text/css"/>
#<item id="myfont" href="css/myfont.otf" media-type="application/x-font-opentype"/>
            for image in page["images"]:
                if self.getImageNameFor(image) in ids:
                    continue
                filename = self.getImageFileNameFor(image)
                mimetype = 'image/png' if filename.find('.png')>0 else 'image/jpeg'
                xml+= '<item id="image_%s" href="%s" media-type="%s"/>\n' % (self.getImageNameFor(image), "Images/"+filename, mimetype)
                ids.append(self.getImageNameFor(image))
        xml+= '</manifest>\n'
        
        xml+= '<spine toc="ncx">\n'
        xml+= '<itemref idref="toc" />'
        for page in pages:
            xml+= '<itemref idref="%s" />' % self.getTitleFor(page)
        xml+= '</spine>\n'
 
        xml+= '</package>'
        return unicode(xml).encode("utf8")

    def getTOCNCXFor(self, pages):
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
        xml+= '<navPoint class="chapter" id="toc" playOrder="1">'
        xml+= '<navLabel><text>Table of Contents</text></navLabel>'
        xml+= '<content src="Text/toc.html"/>'
        xml+= '</navPoint>\n'
        
        i = 2
        for page in pages:
            xml+= '<navPoint class="chapter" id="%s" playOrder="%s">' % (self.getTitleFor(page), str(i))
            xml+= '<navLabel><text>%s</text></navLabel>' % page["title"]
            xml+= '<content src="%s"/>' % self.getPathFor(page)
            xml+= '</navPoint>\n'
            i+=1

        xml+= '\n</navMap>'
        xml+= '</ncx>'
        return unicode(xml).encode("utf8")

    def getTOCHTMLFor(self, pages):
        html = '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">\n'
        html+="<html><head><title>Contents</title></head><body>"
        html+= '<div><center><h2>Contents</h2>'

        for page in pages:
            html+= '<p><a href="%s">%s</a></p>' % (self.getPathFor(page), page["title"])

        html+= '\n</center></div></body></html>'
        return unicode(html).encode("utf8")
