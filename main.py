import json, logging
from google.appengine.ext import blobstore, webapp
from google.appengine.ext.webapp import blobstore_handlers
import model

class HelloWorld(webapp.RequestHandler):
    def get(self):
        self.response.out.write("Hello world!")

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
        new = model.ePubFile(blob = blob_info).put()
        self.redirect('/list')

class List(webapp.RequestHandler):
    def get(self):
        self.response.out.write("<UL>")
        for file in model.ePubFile.all():
            self.response.out.write("<LI><a href='/download?key=%s'>%s</a></LI>" % (file.blob.key(), file.blob.filename))
        self.response.out.write("</UL>")

class Download(blobstore_handlers.BlobstoreDownloadHandler):
    def get(self):
        key = self.request.get('key')
        blob_info = blobstore.BlobInfo.get(key)
        self.send_blob(blob_info, save_as = True)

class View(webapp.RequestHandler):
    def get(self):
        self.response.out.write("View here")

class Edit(webapp.RequestHandler):
    def get(self):
        self.response.out.write("Show edit form")

    def post(self):
        self.response.out.write("Handle edit form")

class Email(webapp.RequestHandler):
    def get(self):
        self.response.out.write("Email here")

class Share(webapp.RequestHandler):
    def get(self):
        self.response.out.write("Share here")

class Quote(webapp.RequestHandler):
    def get(self):
        self.response.out.write("Quote here")

class Account(webapp.RequestHandler):
    def get(self):
        self.response.out.write("Show account")

    def post(self):
        self.response.out.write("Change account")

class Authorize(webapp.RequestHandler):
    def get(self):
        self.response.out.write("Authorize here")

app = webapp.WSGIApplication([
    ('/hello', HelloWorld),
    ('/upload', UploadForm),
    ('/upload_complete', UploadHandler),
    ('/list', List),
    ('/view', View),
    ('/edit', Edit),
    ('/download', Download),
    ('/email', Email),
    ('/share', Share),
    ('/quote', Quote),
    ('/account', Account),
    ('/authorize', Authorize),
    ],
    debug=True)
