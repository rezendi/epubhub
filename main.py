import json, logging, urllib, os, re, zipfile
from google.appengine.api import search, taskqueue, users
from google.appengine.ext import blobstore, db, webapp
from google.appengine.ext.webapp import blobstore_handlers, template
from gaesessions import get_current_session
import model, unpack

def enforce_login(handler):
    session = get_current_session()
    account = session.get("account")
    if account is None:
        handler.redirect("/")

class Main(webapp.RequestHandler):
    def get(self):
        session = get_current_session()
        user = users.get_current_user()
        if user:
            account = db.GqlQuery("SELECT * FROM Account WHERE googleUserID = :1", user.user_id()).get()
            if account is None:
                account_key = session.get("account")
                account = None if account_key is None else db.get(account_key)
            if account is None:
                account = model.Account(googleUserID = user.user_id(), googleEmail = user.email())
                account.put()
            elif account.googleUserID is None:
                account.googleUserID = user.user_id()
                account.put()
            session["account"] = account.key()

        account_key = session.get("account")
        account = None if account_key is None else db.get(account_key)
        if account is None:
            template_values = { "login_url" : users.create_login_url("/")}
            path = os.path.join(os.path.dirname(__file__), 'html/index.html')
            self.response.out.write(template.render(path, template_values))
        else:
            template_values = {
                "login_url" : users.create_login_url("/"),
                "account" : account
            }
            path = os.path.join(os.path.dirname(__file__), 'html/home.html')
            self.response.out.write(template.render(path, template_values))

class LogOut(webapp.RequestHandler):
    def get(self):
        session = get_current_session()
        session.terminate()
        if users.get_current_user():
            self.redirect(users.create_logout_url("/"))
        else:
            self.redirect("/")

class UploadForm(webapp.RequestHandler):
    def get(self):
        enforce_login(self)
        upload_url = blobstore.create_upload_url('/upload_complete')
        self.response.out.write('<html><body>')
        self.response.out.write('<form action="%s" method="POST" enctype="multipart/form-data">' % upload_url)
        self.response.out.write("""Upload File: <input type="file" name="file"><br> <input type="submit" name="submit" value="Submit"> </form></body></html>""")

class UploadHandler(blobstore_handlers.BlobstoreUploadHandler):
    def post(self):
        enforce_login(self)
        upload_files = self.get_uploads('file')  # 'file' is file upload field in the form
        blob_info = upload_files[0]

        epub = model.ePubFile(blob = blob_info, blob_key = blob_info.key())
        epub.put()
        entry = model.LibraryEntry(epub = epub, user = get_current_session().get("account"))
        entry.put()
        
        unpacker = unpack.Unpacker()
        existing, error = unpacker.unpack(epub)

        if error is None:
            epub_key = epub.key() if existing is None else existing.key()
            logging.info("Indexing epub with key %s" % epub_key)
            taskqueue.add(queue_name = 'index', url='/index', countdown=2, params={
                'key':epub_key,
                'user':get_current_session().get("account")
            })
            self.redirect("/list")
        else:
            db.delete(entry)
            blobstore.delete(epub.blob.key())
            db.delete(epub)
            error = "Invalid EPUB file" if error.find("File is not a zip")>0 else error
            self.response.out.write("Upload error: "+error)

class UnpackInternal(webapp.RequestHandler):
    def get(self):
        key = self.request.get('key');
        epub = db.get(key)
        unpacker = unpack.Unpacker()
        unpacker.unpack_internal(epub)

class Index(webapp.RequestHandler):
    def get(self):
        return self.post()

    def post(self):
        user = self.request.get('user')
        key = self.request.get('key')
        epub = db.get(key)
        if epub is None:
            logging.info("Unable to find epub with key %s" % key)
            return
        unpacker = unpack.Unpacker()
        unpacker.index(epub, user, "private")
        if epub.license == "Public Domain" or epub.license == "Creative Commons":
            unpacker.index(epub, user, "public")
        
class List(webapp.RequestHandler):
    def get(self):
        self.response.out.write("<a href='/upload'>Upload</a><br/><hr/>")
        account = get_current_session().get("account")
        entries = model.LibraryEntry.all().filter("user =",db.get(account))
        for entry in entries:
            epub = entry.epub
            self.response.out.write("<b>%s</b><UL>" % epub.blob.filename)
            self.response.out.write("<LI><a href='/edit?key=%s'>Metadata</a></LI>" % epub.key())
            self.response.out.write("<LI><a href='/contents?key=%s'>Contents</a></LI>" % epub.key())
            self.response.out.write("<LI><a href='/manifest?key=%s'>Manifest</a></LI>" % epub.key())
            self.response.out.write("<LI><a href='/delete?key=%s'>Delete</a></LI>" % epub.key())
            self.response.out.write("</UL><hr/>")

class Manifest(blobstore_handlers.BlobstoreDownloadHandler):
    def get(self):
        key = self.request.get('key')
        file = db.get(key)
        self.response.out.write("<b>%s</b><UL>" % file.blob.filename)
        for internal in file.internals():
            self.response.out.write("<LI><a href='/view/%s/%s'>%s</a></LI>" % (file.key(), internal.path, internal.path))
        self.response.out.write("</UL><hr/>")

class Contents(blobstore_handlers.BlobstoreDownloadHandler):
    def get(self):
        key = self.request.get('key')
        epub = db.get(key)
        self.response.out.write("<H1>Table Of Contents</H1>")
        self.response.out.write("<H2>"+epub.title+"</H2><OL>")
        for internal in epub.internals(only_chapters = True):
            self.response.out.write("<LI><a href='/view/%s/%s'>%s</LI>" %(key, internal.path, internal.name))
        self.response.out.write("</OL>")

class Download(blobstore_handlers.BlobstoreDownloadHandler):
    def get(self):
        key = self.request.get('key')
        blob_info = blobstore.BlobInfo.get(key)
        self.send_blob(blob_info, save_as = True)

class View(webapp.RequestHandler):
    def get(self):
        components = self.request.path.split("/")
        if len(components)>1:
            epub_key = components[2]
        if len(components)<4:
            self.redirect("/contents?key="+epub_key)
            return
        epub = db.get(epub_key)
        path = urllib.unquote_plus("/".join(components[3:]))
        internal = epub.internals().filter("path = ",path).get()
        renderer = unpack.Unpacker()
        self.response.headers['Content-Type'] = renderer.contentHeader(internal)
        self.response.out.write(renderer.content(internal))

class Search(webapp.RequestHandler):
    def get(self):
        return self.post()

    def post(self):
        options = search.QueryOptions(limit = 100, snippeted_fields = ['content'])
        query_string = "owners:%s AND (name:%s OR html:%s)" % (get_current_session().get("account"), self.request.get('q'), self.request.get('q'))
        query = search.Query(query_string = query_string, options=options)
        try:
            index = search.Index("private")
            search_results = index.search(query)
            self.response.out.write("<H2>%s Results</H2>" % search_results.number_found)
            for doc in search_results:
                internal = db.get(doc.doc_id)
                if internal is not None:
                    name = internal.path.rpartition("/")[2]
                    self.response.out.write("<LI>%s - <a href='/view/%s/%s'>%s</a>" % (internal.epub.title, internal.epub.key(), internal.path, name))
                    if (len(doc.expressions)>0): #NB doesn't work in dev environment
                        self.response.out.write("<BR/>%s" % doc.expressions[0].value)
        except search.Error:
            self.response.out.write("Error")

class Share(webapp.RequestHandler):
    def post(self):
        quote = model.Quote(
            epub = db.get(self.request.get('epub')),
            file = db.get(self.request.get('file')),
            html = db.Text(self.request.get('html')),
            user = get_current_session().get("account")
        )
        quote.put()
        self.response.headers['Content-Type'] = 'application/json'
        self.response.out.write('{"result":"ok","url":"/quote/%s"}' % quote.key())

class Quotes(webapp.RequestHandler):
    def get(self):
        user = get_current_session().get("account")
        quotes = model.Quote.all().filter("user = ", user).order("epub")
        for quote in quotes:
            html = re.sub('<[^<]+?>', '', quote.html)
            words = html.split(" ")
            words = words[0:6] if len(words) > 7 else words
            text = '"'+" ".join(words)+'"'
            self.response.out.write("<LI><i>%s</i>: <a href='/quote/%s'>%s</a></LI>" % (quote.epub.title, quote.key(), text))

class Quote(webapp.RequestHandler):
    def get(self):
        components = self.request.path.split("/")
        quote_key = urllib.unquote_plus(components[2])
        quote = db.get(quote_key)
        html = '<html><head><script src="/static/jquery-1.7.2.min.js"></script><script src="/static/ephubhost.js"></script>';
        html+= '<script>var epub_share="false", epub_file="%s", epub_title="%s"</script>\n' % (quote.epub.key(), quote.epub.title)
        html+='</head><body>\n'
        html+= quote.html;
        html+= "</body></html>"
        self.response.out.write(html)


class Edit(webapp.RequestHandler):
    def get(self):
        enforce_login(self)
        key = self.request.get('key')
        ePubFile = db.get(key)
        self.response.out.write("<UL>")
        self.response.out.write("<LI>Language: %s</LI>" % ePubFile.language)
        self.response.out.write("<LI>Title: %s</LI>" % ePubFile.title)
        self.response.out.write("<LI>Creator: %s</LI>" % ePubFile.creator)
        self.response.out.write("<LI>Publisher: %s</LI>" % ePubFile.publisher)
        self.response.out.write("<LI>Rights: %s</LI>" % ePubFile.rights)
        self.response.out.write("<LI>Contributor: %s</LI>" % ePubFile.contributor)
        self.response.out.write("<LI>Identifier: %s</LI>" % ePubFile.identifier)
        self.response.out.write("<LI>Description: %s</LI>" % ePubFile.description)
        self.response.out.write("<LI>Date: %s</LI>" % ePubFile.date)
        self.response.out.write("</UL>")

    def post(self):
        enforce_login(self)
        self.response.out.write("Handle edit form")

class Account(webapp.RequestHandler):
    def get(self):
        enforce_login(self)
        self.response.out.write("Show account")

    def post(self):
        enforce_login(self)
        self.response.out.write("Change account")

class Delete(webapp.RequestHandler):
    def get(self):
        confirm = self.request.get('confirm')
        if confirm!="true":
            return
        epub_key = self.request.get('key')
        account = get_current_session().get("account")
        entry = model.LibraryEntry.all().filter("epub = ",db.get(epub_key)).filter("user =",db.get(account)).get()
        logging.info("Got entry %s from %s and %s" % (entry, epub_key, account))
        if entry is not None:
            db.delete(entry)
        self.redirect('/list')

class Clear(webapp.RequestHandler):
    def get(self):
        if not users.is_current_user_admin():
            self.response.out.write("No")
            return
        index = search.Index(name="private")
        for document in index.list_documents():
            index.remove(document.doc_id)
        index = search.Index(name="public")
        for document in index.list_documents():
            index.remove(document.doc_id)

app = webapp.WSGIApplication([
    ('/', Main),
    ('/logout', LogOut),
    ('/upload', UploadForm),
    ('/upload_complete', UploadHandler),
    ('/index', Index),
    ('/list', List),
    ('/unpack_internal', UnpackInternal),
    ('/view/.*', View),
    ('/contents', Contents),
    ('/manifest', Manifest),
    ('/download', Download),
    ('/search', Search),
    ('/share', Share),
    ('/quote/.*', Quote),
    ('/quotes', Quotes),
    ('/edit', Edit),
    ('/account', Account),
    ('/delete', Delete),
    ('/clearindexes', Clear),
    ],
    debug=True)
