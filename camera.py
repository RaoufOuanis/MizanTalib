import threading, time
from PIL import Image, ImageTk
import cv2

CAMERA_AVAILABLE = True

try:
    import winsound
    def beep(freq=1000, dur=100): winsound.Beep(freq, dur)
except Exception:
    def beep(freq=1000, dur=100): pass


def resize_keep_aspect(im, max_w, max_h):
    """إرجاع صورة بحجم مناسب دون تشويه النسبة"""
    w, h = im.size
    ratio = min(max_w / w, max_h / h)
    new_w, new_h = int(w * ratio), int(h * ratio)
    return im.resize((new_w, new_h), Image.LANCZOS)


class CameraScanner:
    def __init__(self, image_label, parent_app, video_source=0):
        self.image_label = image_label
        self.parent_app = parent_app
        self.video_source = video_source
        self.cap = None
        self.running = False
        self.thread = None
        self.current_token = None
        self.last_error = None
        self.qr_detector = cv2.QRCodeDetector()

    def start(self):
        if self.running:
            return True
        if not CAMERA_AVAILABLE:
            self.last_error = (
                "تعذر تفعيل الكاميرا: مكتبة OpenCV غير مثبتة."
            )
            return False
        self.cap = cv2.VideoCapture(self.video_source)
        if not self.cap.isOpened():
            self.cap.release()
            self.cap = None
            self.last_error = "تعذر فتح الكاميرا. تأكد من توفر جهاز تصوير وعدم استخدامه من تطبيق آخر."
            return False
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        self.last_error = None
        return True

    def _loop(self):
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.05)
                continue

            frame = cv2.flip(frame, 1)

            # Détection QR avec OpenCV
            qr_codes = []
            try:
                if hasattr(self.qr_detector, 'detectAndDecodeMulti'):
                    ok, decoded_info, points, _ = self.qr_detector.detectAndDecodeMulti(frame)
                    if ok and decoded_info:
                        qr_codes = [text for text in decoded_info if text]
                else:
                    decoded_text, points, _ = self.qr_detector.detectAndDecode(frame)
                    if decoded_text:
                        qr_codes = [decoded_text]
            except Exception:
                qr_codes = []

            for qr in qr_codes:
                qr = qr.strip()
                if not qr:
                    continue
                outcome = self.parent_app.add_scanned_preview(qr)
                # Play small beep patterns depending on outcome.
                # Use a non-blocking thread for beep sequences so camera loop stays smooth.
                if outcome == "added":
                    threading.Thread(target=lambda: beep(1000, 80), daemon=True).start()
                elif outcome == "duplicate":
                    def dup_beep():
                        try:
                            beep(800, 80)
                            time.sleep(0.08)
                            beep(800, 80)
                        except Exception:
                            pass
                    threading.Thread(target=dup_beep, daemon=True).start()
                elif outcome == "recent":
                    def recent_beep():
                        try:
                            beep(800, 40)
                            time.sleep(0.04)
                            beep(800, 40)
                        except Exception:
                            pass
                    threading.Thread(target=recent_beep, daemon=True).start()
                elif outcome == "missing":
                    threading.Thread(target=lambda: beep(500, 400), daemon=True).start()

            # Affichage vidéo dans Tkinter avec redimensionnement
            try:
                img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                im = Image.fromarray(img)

                if self.image_label.winfo_width() > 50 and self.image_label.winfo_height() > 50:
                    im = resize_keep_aspect(im, self.image_label.winfo_width(), self.image_label.winfo_height())

                imgtk = ImageTk.PhotoImage(im)
                if self.image_label:
                    self.image_label.config(image=imgtk, text="")
                    self.image_label.image = imgtk
            except Exception:
                pass

            time.sleep(0.03)

    def stop(self):
        self.running = False
        time.sleep(0.05)
        if self.cap and self.cap.isOpened():
            self.cap.release()
        self.cap = None

        if self.image_label:
            self.image_label.config(image='', text="📷 الكاميرا متوقفة")
            self.image_label.image = None
