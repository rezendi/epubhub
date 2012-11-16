import json, logging, re
from google.appengine.api import datastore_errors
from google.appengine.ext import blobstore, db

class Book(db.Model):
  timeCreated = db.DateTimeProperty(auto_now_add=True)
  timeEdited = db.DateTimeProperty(auto_now=True)
  creator = db.StringProperty()

class ePubFile(db.Model):
  timeCreated = db.DateTimeProperty(auto_now_add=True)
  timeEdited = db.DateTimeProperty(auto_now=True)
  book = db.ReferenceProperty(Book)
  blob = blobstore.BlobReferenceProperty()
  cover_path = db.StringProperty()
  license = db.StringProperty()
  language = db.StringProperty()
  title = db.StringProperty()
  creator = db.StringProperty()
  publisher = db.StringProperty()
  rights = db.StringProperty()
  contributor = db.StringProperty()
  identifier = db.StringProperty()
  date = db.StringProperty()
  description = db.TextProperty()
  
  def internals(self, only_chapters = False):
    internals = InternalFile.all().filter("epub = ", self)
    if (only_chapters):
      internals = internals.filter("order >",-1)
    return internals.order("order") if only_chapters else internals.order("path")
  
  def entries(self):
    return LibraryEntry.all().filter("epub = ", self)
  
  def entry_count(self):
    return LibraryEntry.all().filter("epub = ", self).count()
  
  def get_cover(self, force_recheck=False):
    if self.cover_path is None or force_recheck:
      potential_cover = None
      for file in self.internals():
        if file.data is not None and file.path.endswith("png") or file.path.endswith("jpg") or file.path.endswith("jpeg"):
          if potential_cover is None or file.name.lower().find("cover") > 0 or len(file.data) > len(potential_cover.data):
            potential_cover = file
      if potential_cover is not None:
        self.cover_path = potential_cover.path
        self.put()
    return self.cover_path

  def isPublicAccess(self):
    return self.license=="Public Domain" or self.license=="Creative Commons"

class InternalFile(db.Model):
  timeCreated = db.DateTimeProperty(auto_now_add=True)
  timeEdited = db.DateTimeProperty(auto_now=True)
  epub = db.ReferenceProperty(ePubFile)
  path = db.StringProperty()
  name = db.StringProperty()
  order = db.IntegerProperty()
  text = db.TextProperty()
  data = db.BlobProperty()

  def isContentFile(self):
    return self.path.endswith("html") or self.path.endswith("xml") and (self.text.find("<html")>0 or self.text.find("<HTML")>0)


class Account(db.Model):
  timeCreated = db.DateTimeProperty(auto_now_add=True)
  timeEdited = db.DateTimeProperty(auto_now=True)
  googleUserID = db.StringProperty()
  googleEmail = db.StringProperty()
  twitterUserID = db.StringProperty()
  twitterHandle = db.StringProperty()
  twitterKey = db.StringProperty()
  twitterToken = db.StringProperty()
  facebookUID = db.StringProperty()
  facebookToken = db.StringProperty()
  facebookInfo = db.TextProperty()
  facebookInterests = db.TextProperty()

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

class PublicRequest(db.Model):
  timeCreated = db.DateTimeProperty(auto_now_add=True)
  timeEdited = db.DateTimeProperty(auto_now=True)
  epub = db.ReferenceProperty(ePubFile)
  user = db.ReferenceProperty(Account)
  supporting_data = db.StringProperty()

#Util methods

def sort_nicely(l):
    convert = lambda text: int(text) if text.isdigit() else text 
    alphanum_key = lambda key: [ convert(c) for c in re.split('([0-9]+)', key) ] 
    return sorted(l, key=alphanum_key )

