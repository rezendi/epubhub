from gaesessions import SessionMiddleware

def webapp_add_wsgi_middleware(app):
  app = SessionMiddleware(app, cookie_key="e88de590-f86e-11e1-a21f-0800200c9a66", no_datastore=True)
  return app