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
            template_values = { "login_url" : users.create_login_url("/") }
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
        template_values = { "upload_url" : blobstore.create_upload_url('/upload_complete') }
        path = os.path.join(os.path.dirname(__file__), 'html/upload.html')
        self.response.out.write(template.render(path, template_values))

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
        account = get_current_session().get("account")
        epubs = []
        entries = model.LibraryEntry.all().filter("user =",db.get(account))
        for entry in entries:
            epubs.append(entry.epub)
        template_values = { "epubs" : epubs }
        path = os.path.join(os.path.dirname(__file__), 'html/books.html')
        self.response.out.write(template.render(path, template_values))

class Manifest(blobstore_handlers.BlobstoreDownloadHandler):
    def get(self):
        key = self.request.get('key')
        epub = db.get(key)
        template_values = {
            "title" : epub.blob.filename,
            "key" : key,
            "files" : epub.internals(),
            "use_name" : False
        }
        path = os.path.join(os.path.dirname(__file__), 'html/contents.html')
        self.response.out.write(template.render(path, template_values))

class Contents(blobstore_handlers.BlobstoreDownloadHandler):
    def get(self):
        key = self.request.get('key')
        epub = db.get(key)
        template_values = {
            "title" : epub.title,
            "key" : key,
            "files" : epub.internals(only_chapters = True),
            "use_name" : True
        }
        path = os.path.join(os.path.dirname(__file__), 'html/contents.html')
        self.response.out.write(template.render(path, template_values))

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
            results = []
            index = search.Index("private")
            search_results = index.search(query)
            for doc in search_results:
                internal = db.get(doc.doc_id)
                if internal is not None:
                    results.append({ "doc" : doc, "internal" : internal })

            template_values = { "results" : results, "result_count" : search_results.number_found }
            path = os.path.join(os.path.dirname(__file__), 'html/search_results.html')
            self.response.out.write(template.render(path, template_values))
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
        results = []
        for quote in quotes:
            html = re.sub('<[^<]+?>', '', quote.html)
            words = html.split(" ")
            words = words[0:6] if len(words) > 7 else words
            text = '"'+" ".join(words)+'"'
            results.append({ "title" : quote.epub.title, "key" : quote.key(), "text" : text})
        template_values = { "quotes" : results }
        path = os.path.join(os.path.dirname(__file__), 'html/quotes.html')
        self.response.out.write(template.render(path, template_values))

class Quote(webapp.RequestHandler):
    def get(self):
        components = self.request.path.split("/")
        quote_key = urllib.unquote_plus(components[2])
        quote = db.get(quote_key)
        template_values = { "quote" : quote }
        path = os.path.join(os.path.dirname(__file__), 'html/quote.html')
        self.response.out.write(template.render(path, template_values))


class Edit(webapp.RequestHandler):
    def get(self):
        key = self.request.get('key')
        epub = db.get(key)
        template_values = { "epub" : epub }
        path = os.path.join(os.path.dirname(__file__), 'html/metadata.html')
        self.response.out.write(template.render(path, template_values))

    def post(self):
        enforce_login(self)
        self.response.out.write("Handle edit form")

class Account(webapp.RequestHandler):
    def get(self):
        enforce_login(self)
        session = get_current_session()
        account_key = session.get("account")
        account = None if account_key is None else db.get(account_key)
        template_values = { "account" : account }
        path = os.path.join(os.path.dirname(__file__), 'html/account.html')
        self.response.out.write(template.render(path, template_values))

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
