
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
  epub = db.ReferenceProperty()
  name = db.StringProperty()
  text = db.TextProperty()
  data = db.BlobProperty()

