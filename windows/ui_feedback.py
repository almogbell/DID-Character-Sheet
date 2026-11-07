"""Small, theme-aware feedback and bounded portrait rendering cache."""
from collections import OrderedDict
import base64
import hashlib
from PySide6.QtCore import Qt, QTimer, QThread, QEventLoop, QRectF
from PySide6.QtGui import QPainter, QPen, QColor, QPixmap
from PySide6.QtWidgets import QWidget, QDialog, QHBoxLayout, QLabel, QApplication, QLayout
from ui_theme import set_themed_stylesheet, theme_color


class LoadingRing(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(30, 30)
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.setInterval(30)
        self.timer.timeout.connect(self.advance)
        self.setAccessibleName('Loading')

    def advance(self):
        self.angle = (self.angle + 12) % 360
        self.update()

    def showEvent(self, event):
        self.timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(5, 5, 20, 20)
        pen = QPen(QColor(theme_color('fantasy_disabled_border')), 3)
        painter.setPen(pen)
        painter.drawEllipse(rect)
        pen.setColor(QColor('#c79843'))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(rect, -self.angle * 16, 255 * 16)
        painter.end()


# DID114_COMPACT_LOADING_NOTICE_V1
class BusyNotice(QDialog):
    """Delayed notice. Owner must call finish on success and failure."""
    def __init__(self, parent, text):
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.done_loading = False
        self.setAccessibleName(text)
        layout = QHBoxLayout(self)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)
        layout.setContentsMargins(18, 14, 20, 14)
        layout.setSpacing(12)
        layout.addWidget(LoadingRing(self), 0, Qt.AlignmentFlag.AlignVCenter)
        self.status_label = QLabel(str(text), self)
        self.status_label.setWordWrap(True)
        self.status_label.setMaximumWidth(360)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.status_label, 1)
        set_themed_stylesheet(self, '''
            QDialog { background: #fffaf0; border: 1px solid #d9bd82; border-radius: 9px; }
            QLabel { color: #765d34; background: transparent; border: none; font-size: 14px; }
        ''')
        self.delay = QTimer(self)
        self.delay.setSingleShot(True)
        self.delay.timeout.connect(self.reveal)
        self.delay.start(250)

    def reveal(self):
        if self.done_loading:
            return
        self.adjustSize()
        owner = self.parentWidget()
        center = owner.mapToGlobal(owner.rect().center()) if owner else None
        if center is not None:
            x = center.x() - self.width() // 2
            y = center.y() - self.height() // 2
            screen = owner.screen() or QApplication.primaryScreen()
            if screen is not None:
                bounds = screen.availableGeometry()
                x = max(bounds.left(), min(x, bounds.right() - self.width() + 1))
                y = max(bounds.top(), min(y, bounds.bottom() - self.height() + 1))
            self.move(x, y)
        self.show()
        self.raise_()

    def reject(self):
        # A loading operation is not canceled by Escape.
        pass

    def closeEvent(self, event):
        event.accept() if self.done_loading else event.ignore()

    def finish(self):
        self.done_loading = True
        self.delay.stop()
        self.hide()
        self.deleteLater()


class ReadTask(QThread):
    def __init__(self, function, parent=None):
        super().__init__(parent)
        self.function = function
        self.result = None
        self.error = None

    def run(self):
        try:
            self.result = self.function()
        except BaseException as error:
            self.error = error


def run_loading_task(owner, message, function):
    """Run detached file/data work. Never pass widget operations to function."""
    task = ReadTask(function, owner)
    notice = BusyNotice(owner, message)
    loop = QEventLoop(owner)
    task.finished.connect(loop.quit)
    enabled = owner.isEnabled()
    owner.setEnabled(False)
    try:
        task.start()
        loop.exec()
        task.wait()
        if task.error is not None:
            raise task.error
        return task.result
    finally:
        notice.finish()
        owner.setEnabled(enabled)
        task.deleteLater()
        loop.deleteLater()


_portrait_cache = OrderedDict()
_portrait_cache_bytes = 0
_CACHE_LIMIT = 32 * 1024 * 1024


def cached_portrait(image_data, width, height):
    """Cache finished thumbnails, not unbounded full-resolution portraits."""
    global _portrait_cache_bytes
    width, height = max(1, width), max(1, height)
    digest = hashlib.sha256(image_data.encode('ascii')).digest()
    key = (digest, width, height)
    if key in _portrait_cache:
        _portrait_cache.move_to_end(key)
        return _portrait_cache[key]
    pixmap = QPixmap()
    pixmap.loadFromData(base64.b64decode(image_data.split(',', 1)[1]))
    if pixmap.isNull():
        raise ValueError('Image could not be displayed.')
    scaled = pixmap.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                           Qt.TransformationMode.SmoothTransformation)
    result = scaled.copy(max(0, (scaled.width()-width)//2), max(0, (scaled.height()-height)//2), width, height)
    cost = result.width()*result.height()*4
    if cost <= _CACHE_LIMIT:
        while _portrait_cache and _portrait_cache_bytes + cost > _CACHE_LIMIT:
            _, old = _portrait_cache.popitem(last=False)
            _portrait_cache_bytes -= old.width()*old.height()*4
        _portrait_cache[key] = result
        _portrait_cache_bytes += cost
    return result


def preserve_sheet_scroll(method):
    from functools import wraps
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        scroll = getattr(self, 'scroll', None)
        if scroll is None or not self.isVisible():
            return method(self, *args, **kwargs)
        bar = scroll.verticalScrollBar()
        value = bar.value()
        character = self.character
        page = getattr(self, 'current_redesign_page', None)
        result = method(self, *args, **kwargs)
        def restore():
            try:
                if self.character is character and getattr(self, 'current_redesign_page', None) == page:
                    bar.setValue(min(value, bar.maximum()))
            except RuntimeError:
                pass
        restore()
        QTimer.singleShot(0, restore)
        return result
    return wrapped
