import json, logging, zipfile
from google.appengine.api import users
from google.appengine.ext import blobstore, db, webapp
from google.appengine.ext.webapp import blobstore_handlers
from gaesessions import get_current_session
import model, unpack

class HelloWorld(webapp.RequestHandler):
    def get(self):
        html = "<UL>"
        session = get_current_session()
        user = users.get_current_user()
        if user:
            account = session.get("account")
            if account is None:
                account = db.GqlQuery("SELECT * FROM Account WHERE userid = :1", user.user_id()).get()
            if account is None:
                account = model.Account(googleUser = user.user_id()).put()
            elif account.googleUser is None:
                account.googleUser = user.user_id()
                account.put()
            session["account"] = account

        if session.get("account") is None:
            html+= "<LI><a href='%s'>Log In with Google</a></LI>" % users.create_login_url("/")
            html+= "<LI><a href='/auth/twitter'>Log In with Twitter</a></LI>"
            html+= "<LI><a href='/auth/facebook'>Log In with Facebook</a></LI>"
        else:
            html+="<LI><a href='/list'>My Books</a></LI>"
            html+="<LI><a href='%s'>Log Out</a></LI>" % users.create_logout_url("/")
        html+= "</UL>"
        self.response.out.write(html)

class UploadForm(webapp.RequestHandler):
    def get(self):
        upload_url = blobstore.create_upload_url('/upload_complete')
        self.response.out.write('<html><body>')
        self.response.out.write('<form action="%s" method="POST" enctype="multipart/form-data">' % upload_url)
        self.response.out.write("""Upload File: <input type="file" name="file"><br> <input type="submit" name="submit" value="Submit"> </form></body></html>""")

class UploadHandler(blobstore_handlers.BlobstoreUploadHandler):
    def post(self):
        upload_files = self.get_uploads('file')  # 'file' is file upload field in the form
        blob_info = upload_files[0]
        file = model.ePubFile(blob = blob_info).put()
        taskqueue.add(url='/unpack', params={'key' : file.key(), 'blob_key' : file.blob.key()})
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

class Unpack(webapp.RequestHandler):
    def get(self):
        key = self.request.get('key')
        blob_key = self.request.get('blob_key')
        epub = zipfile.ZipFile(blobstore.BlobReader(blob_key))
        unpacker = unpack.Unpacker()
        unpacker.unpack(key, epub)

class View(webapp.RequestHandler):
    def get(self):
        components = self.request.path.split("/")
        path = "/".join(components[3:])
        logging.info("path %s" % path)
        internal = model.InternalFile.all().filter("name = ",path).get()
        if internal.data is not None:
            self.response.headers['Content-Type'] = "image"
            self.response.out.write(internal.data)
        else:
            if path.endswith(".css") or path.endswith(".txt") or path.endswith("mimetype"):
                self.response.headers['Content-Type'] = "text/plain"
            elif path.endswith(".xml") or path.endswith(".ncx") or path.endswith(".opf"):
                self.response.headers['Content-Type'] = "application/xml"
            self.response.out.write(internal.text)

class Search(webapp.RequestHandler):
    def get(self):
        self.response.out.write("Search here")

class Email(webapp.RequestHandler):
    def get(self):
        self.response.out.write("Email here")

class Share(webapp.RequestHandler):
    def get(self):
        self.response.out.write("Share here")

class Quote(webapp.RequestHandler):
    def get(self):
        self.response.out.write("Quote here")

class Edit(webapp.RequestHandler):
    def get(self):
        key = self.request.get('key')
        ePubFile = db.get(key)
        self.response.out.write("<UL>")
        self.response.out.write("<LI>Language: %s</LI>" % ePubFile.language)
        self.response.out.write("<LI>Title: %s</LI>" % ePubFile.title)
        self.response.out.write("<LI>Creator: %s</LI>" % ePubFile.creator)
        self.response.out.write("<LI>Publisher: %s</LI>" % ePubFile.publisher)
        self.response.out.write("</UL>")

    def post(self):
        self.response.out.write("Handle edit form")

class Account(webapp.RequestHandler):
    def get(self):
        self.response.out.write("Show account")

    def post(self):
        self.response.out.write("Change account")

class Authorize(webapp.RequestHandler):
    def get(self):
        self.response.out.write("Authorize here")

app = webapp.WSGIApplication([
    ('/', HelloWorld),
    ('/hello', HelloWorld),
    ('/upload', UploadForm),
    ('/upload_complete', UploadHandler),
    ('/unpack', Unpack),
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
    ('/authorize', Authorize),
    ],
    debug=True)
