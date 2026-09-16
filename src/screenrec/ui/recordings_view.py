"""Local recordings catalogue and Qt Multimedia playback."""
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import Qt,QUrl,QRectF
from PySide6.QtGui import QShortcut,QKeySequence,QDesktopServices,QPainter,QColor
from PySide6.QtMultimedia import QMediaPlayer,QAudioOutput,QMediaMetaData
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QPushButton,QLabel,QSlider,
 QLineEdit,QComboBox,QSplitter,QTreeWidget,QTreeWidgetItem,QDialog,QFileDialog,QStyle,QStackedWidget,
 QMessageBox,QApplication,QLineEdit,QPlainTextEdit,QAbstractSpinBox,QComboBox)
from screenrec.logger.logger import get_logger
from screenrec.localization import Translator
from screenrec.config.commands import commands_for
log=get_logger(__name__)

def clock_text(milliseconds):
    seconds=max(0,int(milliseconds)//1000)
    return f"{seconds//3600:02}:{seconds//60%60:02}:{seconds%60:02}"

class PausedFrame(QWidget):
    def __init__(self,owner):
        super().__init__()
        self.owner=owner
        self.setMinimumSize(240,150)
    def paintEvent(self,event):
        painter=QPainter(self)
        painter.fillRect(self.rect(),QColor("black"))
        image=self.owner.frame_image
        if image is not None and not image.isNull():
            size=image.size().scaled(self.size(),Qt.AspectRatioMode.KeepAspectRatio)
            painter.drawImage(QRectF((self.width()-size.width())/2,(self.height()-size.height())/2,size.width(),size.height()),image)
        painter.end()

class Fullscreen(QDialog):
    def __init__(self,owner):
        super().__init__(owner,Qt.WindowType.Window)
        self.owner=owner
        self.setWindowTitle(self.owner.t("player.title"))
        self.layout=QVBoxLayout(self)
        self.layout.setContentsMargins(0,0,0,0)
    def closeEvent(self,event):
        event.ignore()
        self.owner.leave_fullscreen()
    def keyPressEvent(self,event):
        if event.key()==Qt.Key.Key_Escape:
            self.owner.leave_fullscreen()
        else:
            super().keyPressEvent(event)

class RecordingsView(QWidget):
    def __init__(self,directory,parent=None,language="en"):
        super().__init__(parent)
        self.directory=Path(directory)
        self.translator=Translator(language)
        self.current=None
        self.fullscreen=None
        self.recording=False
        self.priming=False
        self.wanted_play=False
        self.frame_image=None
        self.first_image=None
        self.user_muted=False
        root=QVBoxLayout(self)
        row=QHBoxLayout()
        self.folder=QLabel(str(self.directory))
        self.folder.setWordWrap(True)
        refresh=QPushButton(self.t("common.refresh"))
        open_folder=QPushButton(self.t("common.open_folder"))
        row.addWidget(self.folder,1)
        row.addWidget(refresh)
        row.addWidget(open_folder)
        root.addLayout(row)
        self.splitter=QSplitter()
        root.addWidget(self.splitter,1)
        self.library=QWidget()
        library_layout=QVBoxLayout(self.library)
        self.search=QLineEdit()
        self.search.setPlaceholderText(self.t("player.search"))
        self.sort=QComboBox()
        self.sort.addItems([self.t("player.newest"),self.t("player.oldest"),self.t("player.by_name")])
        self.list=QTreeWidget()
        self.list.setHeaderLabels([self.t("player.recording"),self.t("player.date"),self.t("player.mb")])
        self.list.setRootIsDecorated(False)
        self.list.setColumnWidth(0,210)
        library_layout.addWidget(self.search)
        library_layout.addWidget(self.sort)
        library_layout.addWidget(self.list,1)
        self.splitter.addWidget(self.library)
        self.pane=QWidget()
        self.pane_layout=QVBoxLayout(self.pane)
        self.video=QVideoWidget()
        self.video.setMinimumSize(240,150)
        self.video.setStyleSheet("background: black")
        self.screen=QStackedWidget()
        self.screen.addWidget(self.video)
        self.paused_frame=PausedFrame(self)
        self.screen.addWidget(self.paused_frame)
        self.screen.setCurrentIndex(1)
        self.pane_layout.addWidget(self.screen,1)
        self.info=QLabel(self.t("player.select"))
        self.info.setWordWrap(True)
        self.pane_layout.addWidget(self.info)
        self.timeline=QSlider(Qt.Orientation.Horizontal)
        self.timeline.setRange(0,0)
        self.pane_layout.addWidget(self.timeline)
        self.time=QLabel("00:00:00 / 00:00:00")
        self.pane_layout.addWidget(self.time)
        row=QHBoxLayout()
        self.previous=QPushButton()
        self.previous.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaSkipBackward))
        self.previous.setToolTip(self.t("player.previous"))
        self.play=QPushButton()
        self.play.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.play.setToolTip(self.t("player.play_pause"))
        self.stop=QPushButton()
        self.stop.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self.stop.setToolTip(self.t("player.stop"))
        self.next=QPushButton()
        self.next.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaSkipForward))
        self.next.setToolTip(self.t("player.next"))
        back=QPushButton(self.t("player.back"))
        forward=QPushButton(self.t("player.forward"))
        for button in (self.previous,back,self.play,self.stop,forward,self.next):
            row.addWidget(button)
        self.pane_layout.addLayout(row)
        row=QHBoxLayout()
        self.mute=QPushButton(self.t("player.sound"))
        self.mute.setCheckable(True)
        self.mute.setToolTip(self.t("player.mute"))
        self.volume=QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0,100)
        self.volume.setValue(70)
        self.speed=QComboBox()
        for value in (.25,.5,1,1.5,2):
            self.speed.addItem(f"{value:g}×",value)
        self.speed.setCurrentIndex(2)
        row.addWidget(self.mute)
        row.addWidget(self.volume,1)
        row.addWidget(self.speed)
        self.pane_layout.addLayout(row)
        row=QHBoxLayout()
        expand=QPushButton(self.t("player.expand"))
        expand.setCheckable(True)
        full=QPushButton(self.t("player.fullscreen"))
        snapshot=QPushButton(self.t("player.snapshot"))
        self.delete=QPushButton(self.t("player.delete"))
        self.delete.setToolTip(self.t("tip.player_delete"))
        self.delete.setEnabled(False)
        row.addWidget(expand)
        row.addWidget(full)
        row.addWidget(snapshot)
        row.addWidget(self.delete)
        self.pane_layout.addLayout(row)
        self.splitter.addWidget(self.pane)
        self.splitter.setSizes([350,500])
        self.player=QMediaPlayer(self)
        self.audio=QAudioOutput(self)
        self.audio.setVolume(.7)
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video)
        self.player.mediaStatusChanged.connect(self.media_status)
        self.player.errorOccurred.connect(self.media_error)
        self.player.durationChanged.connect(self.duration_changed)
        self.player.positionChanged.connect(self.position_changed)
        self.player.playbackStateChanged.connect(self.state_changed)
        self.player.metaDataChanged.connect(self.metadata_changed)
        self.video.videoSink().videoFrameChanged.connect(self.frame_changed)
        self.timeline.sliderReleased.connect(lambda:self.player.setPosition(self.timeline.value()))
        self.timeline.sliderMoved.connect(lambda p:self.time.setText(clock_text(p)+" / "+clock_text(self.player.duration())))
        self.play.clicked.connect(self.toggle_play)
        self.stop.clicked.connect(self.stop_playback)
        self.previous.clicked.connect(lambda:self.adjacent(-1))
        self.next.clicked.connect(lambda:self.adjacent(1))
        back.clicked.connect(lambda:self.seek(-10000))
        forward.clicked.connect(lambda:self.seek(10000))
        self.volume.valueChanged.connect(lambda value:self.audio.setVolume(value/100))
        self.mute.toggled.connect(self.set_muted)
        self.speed.currentIndexChanged.connect(lambda _:self.player.setPlaybackRate(self.speed.currentData()))
        expand.toggled.connect(self.library.setHidden)
        full.clicked.connect(self.toggle_fullscreen)
        snapshot.clicked.connect(self.snapshot)
        self.delete.clicked.connect(self.delete_current)
        refresh.clicked.connect(lambda:self.refresh())
        open_folder.clicked.connect(lambda:QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.directory.resolve()))))
        self.search.textChanged.connect(self.filter)
        self.sort.currentIndexChanged.connect(lambda _:self.refresh())
        self.list.currentItemChanged.connect(self.selected)
        self.list.itemDoubleClicked.connect(lambda *_:self.toggle_play())
        callbacks={"play_pause":self.toggle_play,"stop_playback":self.stop_playback,"seek_backward":lambda:self.seek(-5000),"seek_forward":lambda:self.seek(5000),"fullscreen":self.toggle_fullscreen,"cancel_or_leave_fullscreen":self.leave_fullscreen,"previous_recording":lambda:self.adjacent(-1),"next_recording":lambda:self.adjacent(1),"snapshot":self.snapshot}
        for command in commands_for("player"):
            shortcut=QShortcut(QKeySequence(command.shortcut),self.pane)
            shortcut.activated.connect(lambda command=command: self._run_shortcut(command, callbacks[command.key]))
        self.refresh()
    def _run_shortcut(self, command, callback):
        focus = QApplication.focusWidget()
        if isinstance(focus, (QLineEdit, QPlainTextEdit, QAbstractSpinBox, QComboBox)):
            return
        callback()

    def t(self,key):
        return self.translator.tr(key)

    def refresh(self,select=None):
        selected=str(Path(select).resolve()) if select else (str(self.current) if self.current else None)
        self.list.blockSignals(True)
        self.list.clear()
        files=[]
        try:
            for path in self.directory.iterdir():
                if path.is_file() and path.suffix.lower() in (".mp4",".mkv",".webm") and not (path.parent/f".{path.name}.recording").exists():
                    try:
                        files.append((path.resolve(),path.stat()))
                    except OSError:
                        pass
            mode=self.sort.currentIndex()
            files.sort(key=lambda item:item[0].name.casefold() if mode==2 else item[1].st_mtime,reverse=mode==0)
            for path,stat in files:
                item=QTreeWidgetItem([path.name,datetime.fromtimestamp(stat.st_mtime).strftime("%d.%m.%Y %H:%M"),f"{stat.st_size/1048576:.1f}"])
                item.setData(0,Qt.ItemDataRole.UserRole,str(path))
                item.setToolTip(0,str(path))
                self.list.addTopLevelItem(item)
                if str(path)==selected:
                    self.list.setCurrentItem(item)
        except OSError as exc:
            self.info.setText(self.t("player.folder_error") + " "+str(exc))
        finally:
            self.list.blockSignals(False)
        self.filter()
        if select and self.list.currentItem():
            self.load(Path(selected))
        if self.current and not self.current.exists():
            self.stop_playback()
            self.player.setSource(QUrl())
            self.current=None
            self.frame_image=None
            self.first_image=None
            self.paused_frame.update()
            self.info.setText(self.t("player.file_missing"))
    def filter(self,*_):
        query=self.search.text().casefold()
        for index in range(self.list.topLevelItemCount()):
            item=self.list.topLevelItem(index)
            item.setHidden(query not in item.text(0).casefold())
    def selected(self,item,*_):
        if item:
            self.load(Path(item.data(0,Qt.ItemDataRole.UserRole)))
    def load(self,path):
        self.priming=False
        self.wanted_play=False
        self.player.stop()
        self.current=path.resolve()
        self.frame_image=None
        self.first_image=None
        self.paused_frame.update()
        self.info.setText(self.current.name)
        self.delete.setEnabled(not self.recording)
        self.priming=not self.recording
        self.audio.setMuted(True)
        self.player.setSource(QUrl.fromLocalFile(str(self.current)))
        log.debug("Player source loaded: %s",self.current)
    def media_status(self,status):
        if status==QMediaPlayer.MediaStatus.LoadedMedia:
            self.metadata_changed()
            if self.priming or self.wanted_play:
                self.player.play()
        elif status==QMediaPlayer.MediaStatus.InvalidMedia:
            self.media_error()
        elif status==QMediaPlayer.MediaStatus.EndOfMedia:
            self.wanted_play=False
    def frame_changed(self,frame):
        if not frame.isValid():
            return
        self.frame_image=frame.toImage()
        if self.first_image is None:
            self.first_image=self.frame_image
        self.paused_frame.update()
        if self.priming:
            self.priming=False
            self.player.pause()
            self.audio.setMuted(self.user_muted)
    def toggle_play(self):
        if self.recording or not self.current:
            return
        self.priming=False
        self.audio.setMuted(self.user_muted)
        if self.player.playbackState()==QMediaPlayer.PlaybackState.PlayingState:
            self.wanted_play=False
            self.player.pause()
        else:
            self.wanted_play=True
            if self.player.position()>=self.player.duration():
                self.player.setPosition(0)
            self.player.play()
    def stop_playback(self):
        self.priming=False
        self.wanted_play=False
        self.player.stop()
        self.player.setPosition(0)
        self.frame_image=self.first_image
        self.paused_frame.update()
    def seek(self,delta):
        if self.current and self.player.isSeekable():
            self.player.setPosition(max(0,min(self.player.duration(),self.player.position()+delta)))
    def adjacent(self,step):
        items=[self.list.topLevelItem(i) for i in range(self.list.topLevelItemCount()) if not self.list.topLevelItem(i).isHidden()]
        current=self.list.currentItem()
        if current in items:
            index=items.index(current)+step
        else:
            index=0
        if 0<=index<len(items):
            self.list.setCurrentItem(items[index])
    def set_muted(self,value):
        self.user_muted=value
        self.audio.setMuted(value or self.priming)
        self.mute.setText(self.t("player.muted") if value else self.t("player.sound"))
    def duration_changed(self,value):
        self.timeline.setRange(0,min(value,2147483647))
        self.position_changed(self.player.position())
    def position_changed(self,value):
        if not self.timeline.isSliderDown():
            self.timeline.setValue(value)
            self.time.setText(clock_text(value)+" / "+clock_text(self.player.duration()))
    def state_changed(self,state):
        self.screen.setCurrentIndex(0 if state==QMediaPlayer.PlaybackState.PlayingState else 1)
        self.paused_frame.update()
        icon=QStyle.StandardPixmap.SP_MediaPause if state==QMediaPlayer.PlaybackState.PlayingState else QStyle.StandardPixmap.SP_MediaPlay
        self.play.setIcon(self.style().standardIcon(icon))
    def metadata_changed(self):
        if self.player.error()!=QMediaPlayer.Error.NoError:
            return
        if not self.current:
            return
        size=self.player.metaData().value(QMediaMetaData.Key.Resolution)
        resolution=f" • {size.width()} × {size.height()}" if size and hasattr(size,"width") else ""
        self.info.setText(self.current.name+resolution)
    def media_error(self,*_):
        self.priming=False
        self.wanted_play=False
        self.info.setText(self.t("player.playback_error") + " "+self.player.errorString())
        log.error("Playback failed: %s",self.player.errorString())
    def toggle_fullscreen(self):
        if self.fullscreen:
            self.leave_fullscreen()
        else:
            self.fullscreen=Fullscreen(self)
            self.fullscreen.layout.addWidget(self.pane)
            self.fullscreen.showFullScreen()
    def leave_fullscreen(self):
        if self.fullscreen:
            dialog=self.fullscreen
            self.fullscreen=None
            self.splitter.addWidget(self.pane)
            dialog.hide()
            dialog.deleteLater()
    def snapshot(self):
        if self.frame_image is None or self.frame_image.isNull():
            self.info.setText(self.t("player.no_frame"))
            return
        path,_=QFileDialog.getSaveFileName(self,self.t("player.snapshot_title"),str(self.directory/"frame.png"),self.t("player.snapshot_filter"))
        if path and not self.frame_image.save(path,"PNG"):
            self.info.setText(self.t("player.snapshot_error"))
    def delete_current(self):
        if self.recording or not self.current:
            return
        path=self.current
        if not path.is_file():
            self.refresh()
            return
        answer=QMessageBox.question(
            self,
            self.t("player.delete"),
            f"Удалить запись «{path.name}»?\n\nФайл будет удалён без возможности восстановления.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.stop_playback()
        self.player.setSource(QUrl())
        try:
            path.unlink()
        except OSError as exc:
            self.info.setText(self.t("player.delete_error") + " "+str(exc))
            log.error("Failed to delete recording %s: %s",path,exc)
            return
        self.current=None
        self.delete.setEnabled(False)
        self.frame_image=None
        self.first_image=None
        self.paused_frame.update()
        self.info.setText(self.t("player.deleted"))
        self.refresh()
    def set_directory(self,directory):
        self.directory=Path(directory)
        self.translator=Translator(language)
        self.folder.setText(str(self.directory))
        self.stop_playback()
        self.player.setSource(QUrl())
        self.current=None
        self.frame_image=None
        self.first_image=None
        self.paused_frame.update()
        self.info.setText(self.t("player.select"))
        self.refresh()
    def set_recording(self,busy):
        previous=self.recording
        self.recording=busy
        if busy:
            self.leave_fullscreen()
            self.stop_playback()
        self.setEnabled(not busy)
        self.delete.setEnabled(bool(self.current) and not busy)
        if previous and not busy and self.current and self.isVisible():
            self.load(self.current)
    def activate(self):
        self.refresh()
        if self.current and self.frame_image is None and not self.recording:
            self.load(self.current)
    def shutdown(self):
        self.leave_fullscreen()
        self.stop_playback()
        self.player.setSource(QUrl())
