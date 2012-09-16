
import json, logging
from google.appengine.api import datastore_errors
from google.appengine.ext import blobstore, db

#Core classes - touch with extreme caution!
class Book(db.Model):
  timeCreated = db.DateTimeProperty(auto_now_add=True)
  timeEdited = db.DateTimeProperty(auto_now=True)
  ccStatus = db.IntegerProperty()
  pdStatus = db.IntegerProperty()
  language = db.StringProperty()
  title = db.StringProperty()
  creator = db.StringProperty()
  publisher = db.StringProperty()

class ePubFile(db.Model):
  timeCreated = db.DateTimeProperty(auto_now_add=True)
  timeEdited = db.DateTimeProperty(auto_now=True)
  book = db.ReferenceProperty(Book)
  blob = blobstore.BlobReferenceProperty()
  blob_key = db.StringProperty()
  language = db.StringProperty()
  title = db.StringProperty()
  creator = db.StringProperty()
  publisher = db.StringProperty()
  
  def internals(self, only_chapters = False):
    query = InternalFile.all().filter("epub = ", self)
    if (only_chapters):
      query = query.filter("order >",0)
    return query.order("order")


class InternalFile(db.Model):
  timeCreated = db.DateTimeProperty(auto_now_add=True)
  timeEdited = db.DateTimeProperty(auto_now=True)
  epub = db.ReferenceProperty(ePubFile)
  path = db.StringProperty()
  name = db.StringProperty()
  order = db.IntegerProperty()
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
  epub = db.ReferenceProperty(ePubFile)
  user = db.ReferenceProperty(Account)

class Quote(db.Model):
  timeCreated = db.DateTimeProperty(auto_now_add=True)
  timeEdited = db.DateTimeProperty(auto_now=True)
  epub = db.ReferenceProperty(ePubFile)
  file = db.ReferenceProperty(InternalFile)
  user = db.ReferenceProperty(Account)
  html = db.TextProperty()
