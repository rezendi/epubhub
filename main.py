import json, logging, urllib, zipfile
from google.appengine.api import search, users
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

        file = model.ePubFile(blob = blob_info)
        file.put()
        entry = model.LibraryEntry(file = file, user = get_current_session().get("account"))
        entry.put()

        epub = zipfile.ZipFile(blobstore.BlobReader(file.blob.key()))
        unpacker = unpack.Unpacker()
        unpacker.unpack(file.key(), epub)
        self.redirect('/list')

class List(webapp.RequestHandler):
    def get(self):
        for file in model.ePubFile.all():
            self.response.out.write("<b>%s</b><UL>" % file.blob.filename)
            self.response.out.write("<LI><a href='/edit?key=%s'>Edit</a></LI>" % file.key())
            self.response.out.write("<LI><a href='/unpack?key=%s&blob_key=%s'>Unpack</a></LI>" % (file.key(),file.blob.key()))
            self.response.out.write("<LI><a href='/contents?key=%s&blob_key=%s'>Contents</a></LI>" % (file.key(),file.blob.key()))
            self.response.out.write("<UL>");
            internals = model.InternalFile.all().filter("epub = ",file)
            for internal in internals:
                self.response.out.write("<LI><a href='/view/%s/%s'>%s</a></LI>" % (file.key(), internal.name, internal.name))
            self.response.out.write("</UL>");
            self.response.out.write("</uL><hr/>")

class Contents(blobstore_handlers.BlobstoreDownloadHandler):
    def get(self):
        key = self.request.get('blob_key')
        blob_info = blobstore.BlobInfo.get(key)
        epub = zipfile.ZipFile(blobstore.BlobReader(key))
        for file in epub.namelist():
            self.response.out.write("<LI>%s</LI>" % str(file))

class Download(blobstore_handlers.BlobstoreDownloadHandler):
    def get(self):
        key = self.request.get('key')
        blob_info = blobstore.BlobInfo.get(key)
        self.send_blob(blob_info, save_as = True)

class View(webapp.RequestHandler):
    def get(self):
        components = self.request.path.split("/")
        path = urllib.unquote_plus("/".join(components[3:]))
        internal = model.InternalFile.all().filter("name = ",path).get()
        renderer = unpack.Renderer()
        self.response.headers['Content-Type'] = renderer.contentHeader(internal)
        self.response.out.write(renderer.content(internal))

class Search(webapp.RequestHandler):
    def get(self):
        return self.post()

    def post(self):
        index = search.Index("chapters")
        query = self.request.get('q')
        try:
            search_results = index.search(query)
            for doc in search_results:
                internal = db.get(doc.doc_id)
                self.response.out.write("<LI><a href='/view/%s/%s'>%s</a></LI>" % (internal.epub.key(), internal.name, internal.name))
        except search.Error:
            self.response.out.write("Error")

class Email(webapp.RequestHandler):
    def get(self):
        enforce_login(self)
        self.response.out.write("Email here")

class Share(webapp.RequestHandler):
    def get(self):
        enforce_login(self)
        self.response.out.write("Share here")

class Quote(webapp.RequestHandler):
    def get(self):
        self.response.out.write("Quote here")

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

app = webapp.WSGIApplication([
    ('/', Main),
    ('/logout', LogOut),
    ('/upload', UploadForm),
    ('/upload_complete', UploadHandler),
    ('/list', List),
    ('/view/.*', View),
    ('/edit', Edit),
    ('/contents', Contents),
    ('/download', Download),
    ('/search', Search),
    ('/email', Email),
    ('/share', Share),
    ('/quote', Quote),
    ('/account', Account),
    ],
    debug=True)
