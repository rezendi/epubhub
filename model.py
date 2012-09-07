
import json, logging
from google.appengine.api import datastore_errors
from google.appengine.ext import blobstore, db

#Core classes - touch with extreme caution!
class ePubFile(db.Model):
  timeCreated = db.DateTimeProperty(auto_now_add=True)
  timeEdited = db.DateTimeProperty(auto_now=True)
  blob = blobstore.BlobReferenceProperty()
  language = db.StringProperty()
  title = db.StringProperty()
  creator = db.StringProperty()
  publisher = db.StringProperty()

class InternalFile(db.Model):
  timeCreated = db.DateTimeProperty(auto_now_add=True)
  timeEdited = db.DateTimeProperty(auto_now=True)
  epub = db.ReferenceProperty(ePubFile)
  name = db.StringProperty()
  text = db.TextProperty()
  data = db.BlobProperty()

class Account(db.Model):
  timeCreated = db.DateTimeProperty(auto_now_add=True)
  timeEdited = db.DateTimeProperty(auto_now=True)
  googleUserID = db.StringProperty()
  twitterUserID = db.StringProperty()
  twitterHandle = db.StringProperty()
  twitterKey = db.StringProperty()
  twitterToken = db.StringProperty()
  facebookUID = db.StringProperty()
  facebookToken = db.StringProperty()

class LibraryEntry(db.Model):
  timeCreated = db.DateTimeProperty(auto_now_add=True)
  timeEdited = db.DateTimeProperty(auto_now=True)
  file = db.ReferenceProperty(ePubFile)
  user = db.ReferenceProperty(Account)
