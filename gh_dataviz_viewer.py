import re, os, io, json, System
import Eto.Forms as ef
import Eto.Drawing as ed
import Rhino.UI
import scriptcontext as sc
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

PORT = 9876

# ── Find HTML and state file ───────────────────────────────────
roots = [
    os.path.join(os.path.expanduser("~"), "OneDrive", "Escritorio"),
    os.path.join(os.path.expanduser("~"), "Desktop"),
    os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop"),
]
html_path  = None
state_path = None
for r in roots:
    h = os.path.join(r, "rhino-dataviz-v2.html")
    if os.path.exists(h):
        html_path  = h
        state_path = os.path.join(r, "rhino_state.json")
        break

if not html_path:
    a = "ERROR: HTML not found"
elif not jsonData:
    a = "Waiting for data..."
else:
    try:
        json_str  = str(jsonData)
        rows      = json.loads(json_str)
        row_count = len(rows)

        # ── Inject live GH data into HTML ──────────────────────
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()
        new_html = re.sub(
            r'(<script id="chart-data" type="application/json">).*?(</script>)',
            lambda m: m.group(1) + "\n" + json_str + "\n" + m.group(2),
            html, flags=re.DOTALL
        )

        # ── Shared references (updated every run, no server restart) ─
        if "dataviz_html_ref" not in sc.sticky:
            sc.sticky["dataviz_html_ref"] = [""]
        sc.sticky["dataviz_html_ref"][0] = new_html

        # Store raw JSON so the /data endpoint can serve live updates
        if "dataviz_data_ref" not in sc.sticky:
            sc.sticky["dataviz_data_ref"] = ["[]"]
        sc.sticky["dataviz_data_ref"][0] = json_str

        # ── Start HTTP server (only once) ───────────────────────
        def make_server(html_ref, data_ref, sp, port):
            class H(BaseHTTPRequestHandler):
                def do_GET(self):
                    if self.path in ('/', '/index.html'):
                        body = html_ref[0].encode('utf-8')
                        self.send_response(200)
                        self.send_header('Content-Type', 'text/html; charset=utf-8')
                        self.send_header('Content-Length', str(len(body)))
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.end_headers()
                        self.wfile.write(body)
                    elif self.path == '/data':
                        # Live data endpoint — polled by HTML every 2 s
                        body = data_ref[0].encode('utf-8')
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json; charset=utf-8')
                        self.send_header('Content-Length', str(len(body)))
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.send_header('Cache-Control', 'no-cache')
                        self.end_headers()
                        self.wfile.write(body)
                    else:
                        self.send_response(404)
                        self.end_headers()

                def do_POST(self):
                    length = int(self.headers.get('Content-Length', 0))
                    body = self.rfile.read(length)
                    try:
                        msg = json.loads(body)
                        try:
                            with io.open(sp, 'r', encoding='utf-8') as f:
                                state = json.load(f)
                        except:
                            state = {'selected': [], 'colors': []}
                        t = msg.get('type', '')
                        d = msg.get('data')
                        if t == 'select':
                            state['selected'] = d
                        elif t == 'colors':
                            state['colors'] = d
                        with io.open(sp, 'w', encoding='utf-8') as f:
                            json.dump(state, f)
                        print("Written:", t, str(d)[:60])
                    except Exception as e:
                        print("POST error:", str(e))
                    self.send_response(200)
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(b'OK')

                def do_OPTIONS(self):
                    self.send_response(200)
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
                    self.send_header('Access-Control-Allow-Headers', 'Content-Type')
                    self.end_headers()

                def log_message(self, fmt, *args):
                    pass  # suppress HTTP logs

            srv = HTTPServer(('localhost', port), H)
            thr = threading.Thread(target=srv.serve_forever)
            thr.daemon = True
            thr.start()
            return srv

        # Only start the server once — reuse if already running
        existing_server = sc.sticky.get("dataviz_server")
        if existing_server is None:
            try:
                server = make_server(sc.sticky["dataviz_html_ref"], sc.sticky["dataviz_data_ref"], state_path, PORT)
                sc.sticky["dataviz_server"] = server
                server_msg = "HTTP server started on :{}.".format(PORT)
            except Exception as e:
                sc.sticky["dataviz_server"] = None
                server_msg = "Server error: " + str(e)
        else:
            server_msg = "HTTP server reused on :{}.".format(PORT)

        panel_url = System.Uri("http://localhost:{}/".format(PORT))

        # ── Open or refresh panel ───────────────────────────────
        existing_form = sc.sticky.get("dataviz_form",  None)
        existing_wv   = sc.sticky.get("dataviz_wv",    None)

        # Check if form is truly usable (not closed/disposed)
        panel_alive = False
        if existing_form is not None and not existing_form.IsDisposed:
            try:
                panel_alive = existing_form.Visible
            except:
                panel_alive = False

        if panel_alive:
            existing_form.Topmost = True
            existing_form.BringToFront()
            existing_wv.Url = panel_url
            a = "Refreshed — {} rows.\n{}".format(row_count, server_msg)
        else:
            form = ef.Form()
            form.Title     = "Data Viz"
            form.Resizable = True
            form.Topmost   = True
            try:
                rw      = Rhino.UI.RhinoEtoApp.MainWindow
                panel_w = 430
                form.Size     = ed.Size(panel_w, rw.Height - 60)
                form.Location = ed.Point(rw.Location.X + rw.Width - panel_w, rw.Location.Y + 30)
            except:
                form.Size = ed.Size(430, 900)

            # Clear sticky when user closes the panel
            def on_closed(s, e):
                sc.sticky["dataviz_form"] = None
                sc.sticky["dataviz_wv"]   = None
            form.Closed += on_closed

            wv     = ef.WebView()
            wv.Url = panel_url
            form.Content = wv
            form.Show()
            form.BringToFront()

            sc.sticky["dataviz_form"] = form
            sc.sticky["dataviz_wv"]   = wv
            a = "Panel opened — {} rows.\n{}".format(row_count, server_msg)

        # ── Init state file if missing ──────────────────────────
        if not os.path.exists(state_path):
            with io.open(state_path, "w", encoding="utf-8") as f:
                json.dump({"selected": [], "colors": []}, f)

    except Exception as e:
        a = "Error: " + str(e)
