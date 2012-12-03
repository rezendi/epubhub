import json, logging, urllib, os, random, re, zipfile
from google.appengine.api import search, taskqueue, users
from google.appengine.ext import blobstore, db, webapp
from google.appengine.ext.webapp import blobstore_handlers, template
from gaesessions import get_current_session
import model, unpack

def enforce_login(handler):
    session = get_current_session()
    account = session.get("account")
    if account is None:
        session["message"] = "Please log in first"
        handler.redirect("/message")

def enforce_rights(handler, epub):
    if epub is None or epub.isPublicAccess():
        return;

    session = get_current_session()
    account = session.get("account")
    if account is None:
        session["message"] = "Please log in first"
        handler.redirect("/message")
        return

    entry = model.LibraryEntry.all().filter("epub = ",epub).filter("user =",db.get(account)).get()
    if entry is None:
        session["message"] = "Sorry! This book isn't public-access, and you don't have it in your library."
        handler.redirect("/message")

def respondWithMessage(handler, message):
    template_values = {
        "current_user" : get_current_session().get("account"),
        "message" : message
    }
    path = os.path.join(os.path.dirname(__file__), 'html/message.html')
    handler.response.out.write(template.render(path, template_values))

class About(webapp.RequestHandler):
    def get(self):
        template_values = {
            "current_user" : get_current_session().get("account"),
        }
        path = os.path.join(os.path.dirname(__file__), 'html/about.html')
        self.response.out.write(template.render(path, template_values))

class Message(webapp.RequestHandler):
    def get(self):
        session = get_current_session()
        message = session.get("message")
        respondWithMessage(self, message)

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
            epubs = model.ePubFile.all().filter("license IN",["Public Domain","Creative Commons"])
            show = []
            for epub in epubs:
                if random.randint(0,1)==1:
                    show.append(epub)
                if len(show)==3:
                    break
            for epub in epubs:
                if len(show)==3:
                    break
                if random.randint(0,1)==1:
                    show.append(epub)
            template_values = {
                "epubs" : show,
                "current_user" : get_current_session().get("account"),
                "login_url" : users.create_login_url("/")
            }
            path = os.path.join(os.path.dirname(__file__), 'html/index.html')
            self.response.out.write(template.render(path, template_values))
        else:
            self.redirect('/list')

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
        template_values = {
            "current_user" : get_current_session().get("account"),
            "upload_url" : blobstore.create_upload_url('/upload_complete')
        }
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
            epub.get_cover()
            self.redirect("/book/"+str(epub.key().id()))
        else:
            db.delete(entry)
            blobstore.delete(epub.blob.key())
            db.delete(epub)
            error = "Invalid EPUB file" if error.find("File is not a zip")>0 else error
            respondWithMessage(self, "Upload error: "+error)

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
        user = get_current_session().get("account")
        user = self.request.get('user') if user is None else str(user)
        key = self.request.get('key')
        epub = db.get(key)
        if epub is None:
            logging.info("Unable to find epub with key %s" % key)
            return
        unpacker = unpack.Unpacker()
        unpacker.index_epub(epub, "private", user)
        if epub.license == "Public Domain" or epub.license == "Creative Commons":
            unpacker.index_epub(epub, "public")
        
class List(webapp.RequestHandler):
    def get(self):
        account = get_current_session().get("account")
        public = account is None or self.request.get('show')=="public"
        if public:
            epubs = model.ePubFile.all().filter("license IN",["Public Domain","Creative Commons"])
        else:
            epubs = []
            entries = model.LibraryEntry.all().filter("user =",db.get(account))
            for entry in entries:
                epubs.append(entry.epub)

        sort = self.request.get('sort')
        sort = "author" if sort is None or len(sort.strip())==0 else sort
        last = self.request.get('last')
        if sort=="author":
            epubs = sorted(epubs, key = lambda epub:epub.creator)
            epubs = reversed(epubs) if last=="author" else epubs
        if sort=="title":
            epubs = sorted(epubs, key = lambda epub:epub.title)
            epubs = reversed(epubs) if last=="title" else epubs
        if sort=="date":
            epubs = sorted(epubs, key = lambda epub:epub.timeCreated)
            epubs = reversed(epubs) if last=="date" else epubs

        results = []
        idx = 0
        for epub in epubs:
            results.append({ 'epub' : epub, 'third' : (idx+1)%3==0 })
            idx+=1
        template_values = {
            "current_user" : get_current_session().get("account"),
            "upload_url" : blobstore.create_upload_url('/upload_complete'),
            "results" : None if len(results)==0 else results,
            "show" : "public" if public else "own",
            "sort" : None if sort==last else sort
        }
        path = os.path.join(os.path.dirname(__file__), 'html/books.html')
        self.response.out.write(template.render(path, template_values))

class Manifest(blobstore_handlers.BlobstoreDownloadHandler):
    def get(self):
        key = self.request.get('key')
        epub = db.get(key)
        template_values = {
            "current_user" : get_current_session().get("account"),
            "title" : epub.blob.filename,
            "key" : key,
            "id" : epub.key().id(),
            "files" : epub.internals(),
            "contents" : False
        }
        path = os.path.join(os.path.dirname(__file__), 'html/contents.html')
        self.response.out.write(template.render(path, template_values))

class Contents(blobstore_handlers.BlobstoreDownloadHandler):
    def get(self):
        components = self.request.path.split("/")
        id = urllib.unquote_plus(components[2])
        epub = model.ePubFile.get_by_id(long(id))
        template_values = {
            "current_user" : get_current_session().get("account"),
            "id" : id,
            "key" : epub.key(),
            "title" : epub.title,
            "cover_path" : epub.cover_path,
            "description" : epub.description,
            "files" : epub.internals(only_chapters = True),
            "contents" : True
        }
        path = os.path.join(os.path.dirname(__file__), 'html/contents.html')
        self.response.out.write(template.render(path, template_values))

class Download(blobstore_handlers.BlobstoreDownloadHandler):
    def get(self):
        key = self.request.get('key')
        epub = db.get(key)
        enforce_rights(self, epub)
        self.send_blob(epub.blob, save_as = True)

class View(webapp.RequestHandler):
    def get(self):
        components = self.request.path.split("/")
        if len(components)>1:
            id = components[2]
        epub = model.ePubFile.get_by_id(long(id))
        enforce_rights(self, epub)
        if len(components)<4:
            self.redirect("/book/"+id)
            return
        path = urllib.unquote_plus("/".join(components[3:]))
        internal = epub.internals().filter("path = ",path).get()
        renderer = unpack.Unpacker()
        self.response.headers['Content-Type'] = renderer.contentHeader(internal)
        self.response.out.write(renderer.content(internal))

class Search(webapp.RequestHandler):
    def get(self):
        return self.post()

    def post(self):
        try:
            include = self.request.get('include')
            query = "(name:%s OR html:%s)" % (self.request.get('q'), self.request.get('q'))
            book = self.request.get('book_filter')
            query = "book:%s AND %s" % (book, query) if book is not None and len(book.strip())>0 else query
            logging.info("Search query "+query)
            sort_opts = search.SortOptions(match_scorer=search.MatchScorer())
            opts = search.QueryOptions(limit = 100, snippeted_fields = ['html'], sort_options = sort_opts)
            results = []
            for indexName in ["private", "public"]:
                if include is not None and len(include.strip())>0 and include.find(indexName)==-1:
                    results.append({'count' : -1, 'results' : [], 'show' : False})
                    continue
                index_results = []
                index = search.Index(indexName)
                active_q = "owners:%s AND %s" % (get_current_session().get("account"), query) if indexName=="private" else query
                search_query = search.Query(query_string = active_q, options=opts)
                search_results = index.search(search_query)
                for doc in search_results:
                    internal = db.get(doc.doc_id)
                    if internal is not None:
                        index_results.append({ "doc" : doc, "internal" : internal })
                results.append({'count' : search_results.number_found, 'results' : index_results, 'show' : True})
    
            template_values = {
                "current_user" : get_current_session().get("account"),
                "private_results" : results[0]['results'],
                "private_count" : results[0]['count'],
                "private_show" : results[0]['show'],
                "public_results" : results[1]['results'],
                "public_count" : results[1]['count'],
                "public_show" : results[1]['show']
            }
            path = os.path.join(os.path.dirname(__file__), 'html/search_results.html')
            self.response.out.write(template.render(path, template_values))
        except search.Error:
            respondWithMessage(self, "Search error")

class Share(webapp.RequestHandler):
    def post(self):
        quote = model.Quote(
            epub = model.ePubFile.get_by_id(long(self.request.get('epub'))),
            file = db.get(self.request.get('file')),
            html = db.Text(self.request.get('html')),
            user = get_current_session().get("account")
        )
        quote.put()
        unpacker = unpack.Unpacker()
        unpacker.index_quote(quote)
        self.response.headers['Content-Type'] = 'application/json'
        self.response.out.write('{"result":"ok","url":"/quote/%s"}' % quote.key().id())

class Quotes(webapp.RequestHandler):
    def get(self):
        user = get_current_session().get("account")
        quotes = model.Quote.all().filter("user = ", user).order("epub")
        results = []
        for quote in quotes:
            html = re.sub('<[^<]+?>', '', quote.html)
            words = html.split(" ")
            words = words[0:6] if len(words) > 7 else words
            text = " ".join(words)
            results.append({ "title" : quote.epub.title, "key" : quote.key(), "text" : text})
        template_values = {
            "current_user" : get_current_session().get("account"),
            "quotes" : results
        }
        path = os.path.join(os.path.dirname(__file__), 'html/quotes.html')
        self.response.out.write(template.render(path, template_values))

class Quote(webapp.RequestHandler):
    def get(self):
        components = self.request.path.split("/")
        id = urllib.unquote_plus(components[2])
        quote = model.Quote.get_by_id(long(id))
        template_values = {
            "current_user" : get_current_session().get("account"),
            "quote" : quote
        }
        path = os.path.join(os.path.dirname(__file__), 'html/quote.html')
        self.response.out.write(template.render(path, template_values))


class Edit(webapp.RequestHandler):
    def get(self):
        components = self.request.path.split("/")
        id = urllib.unquote_plus(components[2])
        epub = model.ePubFile.get_by_id(long(id))
        template_values = {
            "current_user" : get_current_session().get("account"),
            "admin" : users.is_current_user_admin(),
            "edit" : epub.entry_count()<=1,
            "epub" : epub,
            "pr_license" : " selected" if epub.license=="Private" else "",
            "pd_license" : " selected" if epub.license=="Public Domain" else "",
            "cc_license" : " selected" if epub.license=="Creative Commons" else "",
        }
        path = os.path.join(os.path.dirname(__file__), 'html/metadata.html')
        self.response.out.write(template.render(path, template_values))

    def post(self):
        enforce_login(self)
        if self.request.get('license') is not None and not users.is_current_user_admin():
            self.redirect("/")
        epub = db.get(self.request.get('epub_key'))
        if not users.is_current_user_admin() and epub.entry_count()>1:
            self.redirect("/")
        epub.language = self.request.get('language')
        epub.title = self.request.get('title')
        epub.creator = self.request.get('creator')
        epub.publisher = self.request.get('publisher')
        epub.rights = self.request.get('rights')
        epub.contributor = self.request.get('contributor')
        epub.identifier = self.request.get('identifier')
        epub.description = self.request.get('description')
        epub.date = self.request.get('date')

        license = self.request.get('license')
        if epub.license != license:
            if license=="Public Domain" or license=="Creative Commons":
                unpacker = unpack.Unpacker()
                unpacker.index_epub(epub, "public")
            else:
                index = search.Index("public")
                opts = search.QueryOptions(limit = 1000, ids_only = True)
                query = search.Query(query_string = "book:%s" % epub.key(), options=opts)
                docs = index.search(query)
                for doc in docs:
                    index.remove(doc.doc_id)

        epub.license = self.request.get('license')
        epub.put()
        self.redirect("/book/"+str(epub.key().id()))

class Account(webapp.RequestHandler):
    def get(self):
        enforce_login(self)
        session = get_current_session()
        account_key = session.get("account")
        account = None if account_key is None else db.get(account_key)
        template_values = {
            "current_user" : get_current_session().get("account"),
            "account" : account,
            "fbName" : "n/a" if account.facebookInfo is None else json.loads(account.facebookInfo)["name"]
        }
        path = os.path.join(os.path.dirname(__file__), 'html/account.html')
        self.response.out.write(template.render(path, template_values))

    def post(self):
        enforce_login(self)
        self.response.out.write("Change account")

class Request(webapp.RequestHandler):
    def get(self):
        enforce_login(self)
        key = self.request.get('key')
        template_values = {
            "current_user" : get_current_session().get("account"),
            "epub_key" : key,
        }
        path = os.path.join(os.path.dirname(__file__), 'html/request.html')
        self.response.out.write(template.render(path, template_values))

    def post(self):
        enforce_login(self)
        epub_key = self.request.get('epub_key')
        public_request = model.PublicRequest(
            epub = db.get(epub_key),
            user = db.get(get_current_session().get("account")),
        )
        public_request.supporting_data = self.request.get('support').replace("\n","<br/>")
        public_request.put()
        respondWithMessage(self, "Thank you! We have received your request.")

class Delete(webapp.RequestHandler):
    def get(self):
        confirm = self.request.get('confirm')
        if confirm!="true":
            return
        epub_key = self.request.get('key')
        epub = db.get(epub_key)
        account = get_current_session().get("account")
        entry = model.LibraryEntry.all().filter("epub = ",epub).filter("user =",db.get(account)).get()
        if entry is not None:
            db.delete(entry)
            if epub.entry_count()==0:
                for indexName in ["private","public"]:
                    index = search.Index(indexName)
                    opts = search.QueryOptions(limit = 1000, ids_only = True)
                    query = search.Query(query_string = "book:%s" % epub_key, options=opts)
                    docs = index.search(query)
                    for doc in docs:
                        index.remove(doc.doc_id)
                blobstore.delete(epub.blob.key())
                db.delete(epub)

            self.redirect('/list')
        else:
            self.response.out.write("Not permitted")

class DeleteQuote(webapp.RequestHandler):
    def get(self):
        confirm = self.request.get('confirm')
        if confirm!="true":
            return
        quote_key = self.request.get('key')
        quote = db.get(quote_key)
        account = get_current_session().get("account")
        if quote.user.key() == account:
            db.delete(quote)
            search.Index("quotes").remove(quote_key)
            self.redirect('/quotes')
        else:
            self.response.out.write("Not permitted")

class Clear(webapp.RequestHandler):
    def get(self):
        if not users.is_current_user_admin():
            self.response.out.write("No")
            return
        for indexName in ["chapters"]: #["private","public","chapters"]:
            index = search.Index(indexName)
            for doc in index.list_documents(limit=1000, ids_only=True):
                index.remove(doc.doc_id)

app = webapp.WSGIApplication([
    ('/', Main),
    ('/about', About),
    ('/message', Message),
    ('/logout', LogOut),
    ('/upload', UploadForm),
    ('/upload_complete', UploadHandler),
    ('/index', Index),
    ('/books', List),
    ('/list', List),
    ('/unpack_internal', UnpackInternal),
    ('/view/.*', View),
    ('/book/.*', Contents),
    ('/manifest', Manifest),
    ('/download', Download),
    ('/search', Search),
    ('/request', Request),
    ('/share', Share),
    ('/quote/.*', Quote),
    ('/quotes', Quotes),
    ('/edit', Edit),
    ('/edit/.*', Edit),
    ('/account', Account),
    ('/delete', Delete),
    ('/delete_quote', DeleteQuote),
    ('/clearindexes', Clear),
    ],
    debug=True)
