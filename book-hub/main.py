import json, logging, webapp2
from google.appengine.api import taskqueue
import render

class GetGuide(webapp2.RequestHandler):
    def get(self):
        if not self.request.get('dest'):
            self.response.out.write("No destination")
            return
        taskqueue.add(url='/guide', params={'destination' : self.request.get('dest')})
        self.response.out.write("Task launched")


class GuideTask(webapp2.RequestHandler):
    def get(self):
        return self.post()

    def post(self):
        renderer = render.Renderer()
        pages = renderer.renderPage(self.request.get('destination'))

        zipper = render.Zipper()
        [zipfile, zipstream] = zipper.zipPages(pages)
    
        self.response.headers['Content-Type'] ='application/epub+zip'
        title = str(pages[0]["title"].replace(" ","_"))
        self.response.headers['Content-Disposition'] = 'attachment; filename="'+title+'.epub"'
        self.response.out.write(zipstream.getvalue())

app = webapp2.WSGIApplication([
    ('/get', GetGuide),
    ('/guide', GuideTask),
    ],
    debug=True)
