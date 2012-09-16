import json, logging, urllib, re, zipfile
from google.appengine.api import search, taskqueue, users
from google.appengine.ext import blobstore, db, webapp
from google.appengine.ext.webapp import blobstore_handlers
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
                account = model.Account(googleUserID = user.user_id())
                account.put()
            elif account.googleUserID is None:
                account.googleUserID = user.user_id()
                account.put()
            session["account"] = account.key()

        html ="<html><body><UL>"
        account_key = session.get("account")
        account = None if account_key is None else db.get(account_key)
        if account is None:
            html+= "<LI><a href='%s'>Log In with Google</a></LI>" % users.create_login_url("/")
            html+= "<LI><a href='/auth/twitter'>Log In with Twitter</a></LI>"
            html+= "<LI><a href='/auth/facebook'>Log In with Facebook</a></LI>"
        else:
            html+="<LI><a href='/upload'>Upload</a></LI>"
            html+="<LI><a href='/list'>My Books</a></LI>"
            html+="<LI><a href='/quotes'>My Quotes</a></LI>"
            if account.googleUserID is None:
                html+= "<LI><a href='%s'>Attach Google Account</a></LI>" % users.create_login_url("/")
            if account.twitterHandle is None:
                html+= "<LI><a href='/auth/twitter'>Attach Twitter Account</a></LI>"
            if account.facebookUID is None:
                html+= "<LI><a href='/auth/facebook'>Attach Facebook Account</a></LI>"
            html+="<LI><a href='/logout'>Log Out</a></LI>"
        html+= "</UL>"
        html+='<form action="/search" method="POST">'
        html+="""Search: <input type="search" name="q"><br> <input type="submit" name="submit" value="Submit"> </form>"""
        html+="</html></body>"
        self.response.out.write(html)

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

        epub = model.ePubFile(blob = blob_info, blob_key = str(blob_info.key()))
        epub.put()
        entry = model.LibraryEntry(epub = epub, user = get_current_session().get("account"))
        entry.put()

        unpacker = unpack.Unpacker()
        unpacker.unpack(epub)
        taskqueue.add(queue_name = 'index', url='/index', params={'key':epub.key()})
        self.redirect('/list')

class Index(webapp.RequestHandler):
    def get(self):
        return self.post()

    def post(self):
        key = self.request.get('key');
        epub = db.get(key)
        for internal in epub.internals():
            if internal.path.endswith("html"):
                logging.info("Indexing "+internal.path)
                document = search.Document(
                    doc_id=str(internal.key()),
                    fields=[search.HtmlField(name="content",value=internal.text),search.HtmlField(name="path",value=internal.path)]
                )
                search.Index(name="chapters").add(document)

class Unpack(webapp.RequestHandler):
    def get(self):
        key = self.request.get('key');
        epub = db.get(key)
        unpacker = unpack.Unpacker()
        unpacker.unpack_internal(epub)

class List(webapp.RequestHandler):
    def get(self):
        self.response.out.write("<a href='/upload'>Upload</a><br/><hr/>")
        for file in model.ePubFile.all():
            self.response.out.write("<b>%s</b><UL>" % file.blob.filename)
            self.response.out.write("<LI><a href='/edit?key=%s'>Metadata</a></LI>" % file.key())
            #self.response.out.write("<LI><a href='/unpack?key=%s&blob_key=%s'>Unpack</a></LI>" % (file.key(),file.blob.key()))
            self.response.out.write("<LI><a href='/contents?key=%s'>Contents</a></LI>" % file.key())
            self.response.out.write("<LI><a href='/manifest?key=%s'>Manifest</a></LI>" % file.key())
            #self.response.out.write("<LI>%s %s</LI>" % (file.blob.size, file.blob.key()))
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
            return
        if len(components)==4:
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
        query = search.Query(query_string = self.request.get('q'), options=options)
        try:
            index = search.Index("chapters")
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

class Clear(webapp.RequestHandler):
    def get(self):
        if not users.is_current_user_admin():
            self.response.out.write("No")
            return
        index = search.Index(name="chapters")
        for document in index.list_documents():
            index.remove(document.doc_id)

app = webapp.WSGIApplication([
    ('/', Main),
    ('/logout', LogOut),
    ('/upload', UploadForm),
    ('/upload_complete', UploadHandler),
    ('/index', Index),
    ('/list', List),
    ('/unpack', Unpack),
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
    ('/clear', Clear),
    ],
    debug=True)
