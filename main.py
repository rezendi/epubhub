import json, logging, webapp2

class HelloWorld(webapp2.RequestHandler):
    def get(self):
        self.response.out.write("Hello world!")

class Upload(webapp2.RequestHandler):
    def get(self):
        self.response.out.write("Form here")

    def post(self):
        self.response.out.write("Get zip, store zip, start unpacking it")

class List(webapp2.RequestHandler):
    def get(self):
        self.response.out.write("List here")

class View(webapp2.RequestHandler):
    def get(self):
        self.response.out.write("View here")

class Edit(webapp2.RequestHandler):
    def get(self):
        self.response.out.write("Show edit form")

    def post(self):
        self.response.out.write("Handle edit form")

class Download(webapp2.RequestHandler):
    def get(self):
        self.response.out.write("Download here")

class Email(webapp2.RequestHandler):
    def get(self):
        self.response.out.write("Email here")

class Share(webapp2.RequestHandler):
    def get(self):
        self.response.out.write("Share here")

class Quote(webapp2.RequestHandler):
    def get(self):
        self.response.out.write("Quote here")

class Account(webapp2.RequestHandler):
    def get(self):
        self.response.out.write("Show account")

    def post(self):
        self.response.out.write("Change account")

class Authorize(webapp2.RequestHandler):
    def get(self):
        self.response.out.write("Authorize here")

app = webapp2.WSGIApplication([
    ('/hello', HelloWorld),
    ('/upload', Upload),
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
