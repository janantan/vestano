from vestano import app as application
import os
os.environ['PATH'] += os.pathsep + '/usr/local/bin'

if __name__ == "__main__":
        application.run()