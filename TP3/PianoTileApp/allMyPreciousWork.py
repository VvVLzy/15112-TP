from cmu_112_graphics import * # from CMU 15-112 F19: http://www.cs.cmu.edu/~112/
from tkinter import *
from PIL import Image
import matplotlib.pyplot as plt
import time
import mido
import pyaudio
import numpy as np
import aubio
import copy

# I learned how to read and write txt file from:
# https://stackabuse.com/reading-and-writing-lists-to-a-file-in-python/
# The background picture in the splash screen is from google image

# these two function is from 112 website:
def almostEqual(d1, d2, epsilon=10**-7):
    # note: use math.isclose() outside 15-112 with Python version 3.5 or later
    return (abs(d2 - d1) < epsilon)

import decimal
def roundHalfUp(d):
    # Round to nearest with ties going away from zero.
    rounding = decimal.ROUND_HALF_UP
    # See other rounding options here:
    # https://docs.python.org/3/library/decimal.html#rounding-modes
    return int(decimal.Decimal(d).to_integral_value(rounding=rounding))


# we don't need x-value for our plot
class Plot(object):
    def __init__(self, y, xLabel, yLabel, title):
        self.y = y
        self.xLabel = xLabel
        self.yLabel = yLabel
        self.title = title

    def plot(self):
        plt.plot(self.y) 
        plt.xlabel(self.xLabel)
        plt.ylabel(self.yLabel)
        plt.title(self.title)
        plt.show()

# all of the demo midi files in this project is from musescore.com
# but you can try any other midi files from anywhere
class Sheet(object):
    def __init__(self, midiFile):
        self.sheetFile = mido.MidiFile(midiFile)
        self.tpb = self.sheetFile.ticks_per_beat
        self.metaMsg = [ ] # the technical message of the file
        self.rightHandMsg = [ ]
        self.leftHandMsg = [ ]
        self.organizeTrackAndMessage()
        self.tempo, self.bpm = self.getTempoAndBPM()
        self.tickPer1Millisecond = self.tpb * self.bpm / 100000
        self.allKeyInfo = self.getAllKeyInfo()

    def organizeTrackAndMessage(self):
        for i, track in enumerate(self.sheetFile.tracks):
            if (i == 0): # right hand track
                for msg in track:
                    if (msg.type == 'note_on' or msg.type == 'note_off'):
                        self.rightHandMsg.append(msg)
                    else:
                        self.metaMsg.append(msg)
            else: # left hand track
                for msg in track:
                    if (msg.type == 'note_on' or msg.type == 'note_off'):
                        self.leftHandMsg.append(msg)
                    else:
                        self.metaMsg.append(msg)

    def getTempoAndBPM(self):
        for msg in self.metaMsg:
            if (msg.type == 'set_tempo'):
                tempo = msg.tempo
                bpm = roundHalfUp(mido.tempo2bpm(msg.tempo))
        return tempo, bpm

    def getAllKeyInfo(self):
        pianoKeys = [ ]
        pianoTick = [ ]
        for msg in self.rightHandMsg:
            #note = aubio.midi2note(msg.note)
            pianoKeys.append((msg.note, msg.velocity)) # velocity is the volume
            pianoTick.append(msg.time)

        pianoTime = [ ]
        for tick in pianoTick:
            time = mido.tick2second(tick, self.tpb, self.tempo)
            pianoTime.append(time)

        allKeyInfo = [ ]
        for i in range(len(pianoKeys)):
            note, vol = pianoKeys[i]
            duration = pianoTime[i]
            allKeyInfo.append((note, vol, duration))
        return allKeyInfo

# this class is original, but the method to open up a stream is from:
# https://github.com/aubio/aubio/blob/master/python/demos/demo_pyaudio.py
class Stream(object):
    def __init__(self):
        # initialise pyaudio
        self.p = pyaudio.PyAudio()
        self.buffer_size = 1024
        self.pyaudio_format = pyaudio.paFloat32
        self.n_channels = 1
        self.samplerate = 22050 # sample collect per second
        self.tolerance = 0.8
        self.win_s = 4096 # fft size
        self.hop_s = self.buffer_size # hop size
        self.openStream()

    def openStream(self):
        self.setUpStream()
        self.setUpPitch()

    def setUpStream(self):
        self.stream = self.p.open(format=self.pyaudio_format,
                                  channels=self.n_channels,
                                  rate=self.samplerate,
                                  input=True,
                                  frames_per_buffer=self.buffer_size)

    def setUpPitch(self):
        self.pitch_o = aubio.pitch("default", self.win_s, self.hop_s, self.samplerate)
        self.pitch_o.set_unit("midi")
        self.pitch_o.set_tolerance(self.tolerance)

    # use inside the while-loop of real-time detection
    def readPitch(self):
        audiobuffer = self.stream.read(self.buffer_size)
        signal = np.fromstring(audiobuffer, dtype=np.float32)
        pitch = roundHalfUp(float(self.pitch_o(signal)[0]))
        return pitch

    def closeStream(self):
        self.stream.stop_stream()
        self.stream.close()
        #print('Done!')

    def closeClass(self):
        self.p.terminate()
        #print('Done!')
    
    def checkKeyPlayed(self, target, targetTime):
        targetValue = 0
        startTime = time.time()
        while True:
            timeElapsed = time.time() - startTime
            # if the player don't find the key in five seconds, return.
            if (timeElapsed > 5): return 0
            else:
                pitch = self.readPitch()
                note = aubio.midi2note(pitch)
                #storage.append(pitch)
                #print("{}".format(note))
                # return the note if the correct note is played
                if (pitch in target):
                    targetValue += 1
                    if (targetValue == targetTime):
                        #print(f'Target note {pitch} detected!')
                        return pitch
    
    # using dictionary to keep track of total number detected
    def getKeyPlayed(self, targetTime):
        keysPlayed = dict()
        startTime = time.time()
        while True:
            timeElapsed = time.time() - startTime
            # if the player don't find the key in five seconds, return.
            if (timeElapsed > 5): return 0
            else:
                pitch = self.readPitch()
                note = aubio.midi2note(pitch)
                timesDetected = keysPlayed.get(pitch, 0) + 1
                # return the detected note
                if (pitch != 0 and timesDetected == targetTime):
                    return pitch
                keysPlayed[pitch] = timesDetected

    # return only when the consecutive number reach the bar
    def getKeyPlayed(self, targetTime, period):
        previousKey = 0
        keyPressTime = 0
        startTime = time.time()
        while True:
            timeElapsed = time.time() - startTime
            # if the player don't find the key in five seconds, return.
            if (timeElapsed > period): return 0
            else:
                pitch = self.readPitch()
                note = aubio.midi2note(pitch)
                if (pitch != 0 and pitch == previousKey):
                    keyPressTime += 1
                    if (keyPressTime == targetTime):
                        return pitch
                else:
                    keyPressTime = 0
                    previousKey = pitch

    def getLengthOfKeyPlayed(self, target, period):
        startTime = time.time()
        keyStartTime = None
        keyEndTime = None
        while True:
            timeElapsed = time.time() - startTime
            # if the player don't find the key in five seconds, return.
            if (timeElapsed > period): return 0
            else:
                pitch = self.readPitch()
                note = aubio.midi2note(pitch)
                if (pitch == target and keyStartTime == None):
                    keyStartTime = time.time()
                elif (keyStartTime != None and pitch != target):
                    keyEndTime = time.time()
                    return keyEndTime - keyStartTime

    # target should be a list of values
    def targetNoteBeingPlayed(self, target):
        pitch = self.readPitch()
        #print(aubio.midi2note(pitch), pitch in target)
        return pitch in target

class Keyboard(object):
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.margin = 5
        self.keysBeingPressed = set() # midi of the keys being pressed
        self.wrongKeyPressed = 0
        self.initializeKeyboard()
        self.storeKeyPositions()
        self.createMidiPositionMapping()
        self.seperateWhiteAndBlackMidi()

    def initializeKeyboard(self):
        self.whiteKeys = 52
        self.blackKeys = 36
        self.whiteKeyWidth = (self.width - 2 * self.margin) / self.whiteKeys
        self.blackKeyWidth = self.whiteKeyWidth / 2
        self.octaveWidth = self.whiteKeyWidth * 7
        self.keyHeight = self.height / 5
        self.blackKeyHeight = self.keyHeight * 2 / 3
        self.keyTop = self.height - self.keyHeight
        
    def storeKeyPositions(self):
        self.whiteKeyPositions = set() 
        self.blackKeyPositions = set()
        self.storeWhiteKeyPositions()
        self.storeBlackKeyPositions()
        self.keyPositions = sorted(self.whiteKeyPositions.union(self.blackKeyPositions))

    def createMidiPositionMapping(self):
        Keyboard.midiToPositions = dict()
        startingMidi = 21
        for i in range(self.whiteKeys + self.blackKeys):
            Keyboard.midiToPositions[startingMidi + i] = self.keyPositions[i]

    def seperateWhiteAndBlackMidi(self):
        self.whiteMidiToPositions = dict()
        self.blackMidiToPositions = dict()
        for key in self.midiToPositions:
            keyPosition = self.midiToPositions[key]
            if (keyPosition in self.whiteKeyPositions):
                self.whiteMidiToPositions[key] = keyPosition
            else:
                self.blackMidiToPositions[key] = keyPosition

    # we only have to store the x-values for each key since there y will be the same
    def storeWhiteKeyPositions(self):
        # this is simply adapted from the draw function and extract x-coordinates
        for i in range(52):
            x0 = i * self.whiteKeyWidth + self.margin
            x1 = (i + 1) * self.whiteKeyWidth + self.margin
            self.whiteKeyPositions.add((x0, x1))

    # same as above
    def storeBlackKeyPositions(self):
        # this is the leftiest special one
        x0 = self.margin + self.blackKeyWidth * 1.5
        x1 = x0 + self.blackKeyWidth
        self.blackKeyPositions.add((x0, x1))
        #self.keyPositions.append((x0, x1))
        for octave in range(7): # 7 octaves
            startX = self.margin + 2 * self.whiteKeyWidth + 1.5 * self.blackKeyWidth + octave * self.octaveWidth
            for i in range(6):
                if (i != 2):
                    x0 = startX + i * self.whiteKeyWidth
                    x1 = startX + i * self.whiteKeyWidth + self.blackKeyWidth
                    self.blackKeyPositions.add((x0, x1))

    def drawWhiteKeys(self, canvas):
        y0, y1 = self.keyTop, self.height
        for midi in self.whiteMidiToPositions:
            x0, x1 = self.whiteMidiToPositions[midi]
            if (midi in self.keysBeingPressed): fill = 'cyan'
            elif (midi == self.wrongKeyPressed): fill = 'red'
            else: fill = 'white'
            canvas.create_rectangle(x0, y0, x1, y1, fill=fill)

    def drawBlackKeys(self, canvas):
        y0, y1 = self.keyTop, self.keyTop + self.blackKeyHeight
        for midi in self.blackMidiToPositions:
            x0, x1 = self.blackMidiToPositions[midi]
            if (midi in self.keysBeingPressed): fill = 'cyan'
            elif (midi == self.wrongKeyPressed): fill = 'red'
            else: fill = 'black'
            canvas.create_rectangle(x0, y0, x1, y1, fill=fill)

    def drawKeyNotations(self, canvas):
        for midi in self.midiToPositions:
            x0, x1 = self.midiToPositions[midi]
            x = (x0 + x1) / 2
            note = aubio.midi2note(midi)
            canvas.create_text(x, self.height - 120,
                               text=note, font='Avenir 8', fill='white')

    def pressKey(self, midi):
        self.keysBeingPressed.add(midi)

    def releaseKey(self, midi):
        self.keysBeingPressed.remove(midi)

class Tile(object):
    def __init__(self, midi, command=0, delay=0):
        self.midi = midi
        self.command = True if (command > 0) else False
        self.delay = delay
        self.length = 0
        self.x0, self.x1 = Keyboard.midiToPositions[midi]
        self.y0 = 0
        self.y1 = 0
        self.speed = 1
        self.color = 'yellow'
        self.isGrowing = True
        self.touchedKey = False

    def growOrMove(self):
        if (self.isGrowing):
            self.length += self.speed
            self.y1 = self.y0 + self.length
        else:
            self.y0 += self.speed
            self.y1 += self.speed

    def touchKeyboard(self, keyboard):
        if (self.y1 > keyboard.keyTop and not self.touchedKey):
            self.y1 = keyboard.keyTop
            self.color = 'cyan'
            self.touchedKey = True
            return True
        return False

    def draw(self, canvas):
        canvas.create_rectangle(self.x0, self.y0, self.x1, self.y1,
                                fill=self.color)

    def getHashables(self):
        return (self.x0, self.y0, self.x1, self.y1)

    def __eq__(self, other):
        return isinstance(other, Tile) and (hash(self) == hash(other))

    def __hash__(self):
        return hash(self.getHashables())

    def __repr__(self):
        note = aubio.midi2note(self.midi)
        return note

# the tile in the compose mode
class ComposedTile(Tile):
    def __init__(self, midi, keyTop):
        super().__init__(midi)
        self.keyTop = keyTop
        #self.x0, self.x1 = ComposeMode.midiToPositions[midi]
        self.color = 'cyan'
        self.y1 = keyTop
        self.y0 = keyTop - self.length

    def growOrMove(self):
        if (self.isGrowing):
            self.length += self.speed
            self.y0 = self.y1 - self.length
        else:
            self.y0 -= self.speed
            self.y1 -= self.speed

    def clicked(self, x, y):
        return self.x0 < x < self.x1 and self.y0 < y < self.y1


# clickable button in the splash screen mode
class Button(object):
    def __init__(self, cx, cy, width, height, text):
        self.cx = cx
        self.cy = cy
        self.width = width
        self.height = height
        self.text = text
        self.font = f'SignPainter {self.height} bold'
        self.getBounds()

    def getBounds(self):
        self.x0, self.y0 = self.cx - self.width, self.cy - self.height
        self.x1, self.y1 = self.cx + self.width, self.cy + self.height

    def draw(self, canvas):
        canvas.create_rectangle(self.x0, self.y0, self.x1, self.y1,
                                fill='light gray', outline='white', width=3)
        canvas.create_text(self.cx, self.cy, text=self.text,
                           fill='black', font=self.font)

    def clicked(self, x, y):
        return self.x0 < x < self.x1 and self.y0  < y < self.y1

class Background(object):
    def __init__(self, cx, scrollX):
        self.scrollX = scrollX
        self.cx = cx

# this animation framework and modal app framework is from CMU 15-112 F19: http://www.cs.cmu.edu/~112/
class PracticeMode(Mode):
    @staticmethod
    def convertStringToTuple(s):
        s = s[1:-1] # gets rid of brackets
        L = [ ]
        index = 0
        for element in s.split(', '):
            if (index == 0 or index == 1): # must be int
                L.append(int(element))
            else:
                L.append(float(element))
            index += 1
        return tuple(L)

    def appStarted(self):
        self.setUpKeyboard()
        self.setUpStream()
        self.restart()

    def restart(self):
        self.setUpBasicInfo()
        self.keyboard.keysBeingPressed = set()
        if (self.getFileName()): # if the player enter something
            self.getFileToPlay(self.fileName)
        else:
            self.app.setActiveMode(self.app.splashScreenMode)
    
    def setUpBasicInfo(self):
        self.timerDelay = 1
        self.resetTimer()
        self.printErrorMessage = False
        self.pause = False
        self.animationStop = False
        self.nonStop = False
        self.playerStuck = False
        self.timeStop = 0
        self.wrongKeys = 0
        self.timeStart = 0
        self.numberOfKeysPlayed = 0
        self.currentCommands = [ ] # put here to avoid crashing
        self.tiles = [ ]
        self.keysToPlay = [ ] # in midi
        self.keysBeingPlayed = [ ]
        self.timeUsedPerKey = [ ]

    def setUpKeyboard(self):
        self.keyboard = Keyboard(self.width, self.height)

    def getCommands(self):
        self.commandIndex = 0
        self.currentCommands = self.getNewCommand()

    def setUpStream(self):
        self.stream = Stream()
    
    def getFileName(self):
        self.fileName = self.getUserInput('Enter file name (remember to include ".mid"):')
        if (self.fileName == None): return False
        return True

    def getFileToPlay(self, fileName):
        if (fileName.endswith('.mid')):
            try:
                self.sheet = Sheet(fileName)
                self.commands = self.sheet.allKeyInfo
                self.getCommands()
            except: # if the file is not in the folder
                self.printErrorMessage = True
        elif (fileName.endswith('.txt')): # player's own file
            try:
                self.commands = [ ]
                with open(fileName, 'r') as filehandle:
                    filecontents = filehandle.readlines()
                    for line in filecontents:
                        # remove linebreak which is the last character of the string
                        command = line[:-1]
                        # add item to the list
                        command = PracticeMode.convertStringToTuple(command)
                        self.commands.append(command)
                self.getCommands()
            except: # if the file is not in the folder
                self.printErrorMessage = True
        elif (fileName in list(key for key in ComposeMode.works)):
            self.commands = ComposeMode.works[fileName]
            self.getCommands()
        else: # the player enter something which doesnt make sense at all :(
            self.printErrorMessage = True

    def resetTimer(self):
        self.startTime = time.time()
        self.audioTime = 0

    def keyPressed(self, event):
        if (event.key == 'Space' and self.nonStop):
            self.animationStop = not self.animationStop
            if (self.animationStop):
                self.timeStart = time.time()
            else:
                self.audioTime = time.time() - self.timeStart
                self.timeStart = 0
        elif (event.key == 'n'):
            self.nonStop = not self.nonStop
        elif (event.key == 'q'):
            self.app.setActiveMode(self.app.splashScreenMode)
        elif (event.key == 'p'):
            self.plotFeedBack()
        elif (event.key == 'r'):
            self.restart()
        elif (event.key == 'h'):
            self.app.setActiveMode(self.app.practiceHelpMode)
        elif (self.playerStuck):
            if (event.key == 's'): # skip this key
                self.marchThroughKey(self.keysToPlay[0])
                self.timeUsedPerKey.append(time.time() - self.keyTimer)
                self.keyTimer = time.time() # in case it's a chord
                self.playerStuck = False
            elif (event.key == 'k'): # the player wants to keep trying
                self.resetErrorCounter()
                self.playerStuck = False

    def plotFeedBack(self):
        n = len(self.timeUsedPerKey) # the number of total keys
        if (n == 0): return
        avgTime = sum(self.timeUsedPerKey) / n
        y = list(time for time in self.timeUsedPerKey)
        xLabel = f'Relative Position (total number of keys: {n})'
        yLabel = 'Time Spend Per Key (seconds)'
        title = 'Average Time Per Key: %0.2f seconds' % avgTime
        p = Plot(y, xLabel, yLabel, title)
        p.plot()

    def detectKey(self, tolerance):
        self.stream.openStream()
        keyPlayed = self.stream.checkKeyPlayed(self.keysToPlay, tolerance) # 5 is to reduce tolerance
        if (keyPlayed in self.keysToPlay):
            self.keysBeingPlayed.append(keyPlayed)
            self.keyboard.pressKey(keyPlayed)
            self.keysToPlay.remove(keyPlayed)
        self.stream.closeStream()

    def resetErrorCounter(self):
        self.keyboard.wrongKeyPressed = 0
        self.timeStop = 0
        self.wrongKeys = 0

    def marchThroughKey(self, keyPlayed):
        self.resetErrorCounter()
        self.keysBeingPlayed.append(keyPlayed)
        self.keyboard.pressKey(keyPlayed)
        self.keysToPlay.remove(keyPlayed)

    # only return True when the correct key is played
    def detectKey(self, tolerance, period):
        if (self.playerStuck or self.keysToPlay == [ ]): return
        self.stream.openStream()
        keyPlayed = self.stream.getKeyPlayed(tolerance, period) # 5 is to reduce tolerance
        self.stream.closeStream()
        if (keyPlayed in self.keysToPlay):
            self.marchThroughKey(keyPlayed)
            self.timeUsedPerKey.append(time.time() - self.keyTimer)
            self.keyTimer = time.time() # in case it's a chord
        elif (keyPlayed != 0): # played the wrong key
            self.keyboard.wrongKeyPressed = keyPlayed
            self.wrongKeys += 1
        else: # didnt play for 5 seconds
            self.keyboard.wrongKeyPressed = 0
            self.timeStop += 1

    def addAndEditTiles(self, command):
        midi, press, delay = command
        if (press):
            newTile = Tile(midi, press, delay)
            self.tiles.append(newTile)
        else:
            for tile in self.tiles:
                if (tile.midi == midi):
                    tile.isGrowing = False

    def getNewCommand(self):
        if (self.commandIndex == len(self.commands)): return [ ]
        end = self.commandIndex + 1
        while (end < len(self.commands) and self.commands[end][2] == 0):
            end += 1
        commands = self.commands[self.commandIndex : end]
        self.commandIndex = end
        return commands

    def executeAndUpdateCommand(self):
        if (self.currentCommands == [ ]): return
        timeElapsed = time.time() - self.startTime - self.audioTime
        if (timeElapsed > self.currentCommands[0][2]):
            for command in self.currentCommands:
                self.addAndEditTiles(command)
            self.currentCommands = self.getNewCommand()
            self.resetTimer()

    def growOrDropAllTiles(self):
        for tile in self.tiles:
            tile.growOrMove()

    def nonStopScroll(self, tile):
        if (self.nonStop):
            self.keysBeingPlayed.append(tile.midi)
            self.keyboard.pressKey(tile.midi)
            self.keysToPlay.remove(tile.midi)

    def checkHitBottom(self):
        for tile in self.tiles:
            if (tile.touchKeyboard(self.keyboard)):
                self.keysToPlay.append(tile.midi)
                self.keyTimer = time.time()
                self.pause = True if (not self.nonStop) else False
                self.nonStopScroll(tile)
                self.numberOfKeysPlayed += 1

    def removeTile(self):
        temp = copy.deepcopy(self.tiles)
        for tile in self.tiles:
            if (tile.y0 > self.keyboard.keyTop):
                temp.remove(tile)
                self.keysBeingPlayed.remove(tile.midi)
                self.keyboard.releaseKey(tile.midi)
        self.tiles = temp

    def timerFired(self):
        if (self.pause):
            if (self.timeStart == 0):
                self.timeStart = time.time() # the time spend detecting audio should be taken into account
            self.detectKey(3, 5)
            if (len(self.keysToPlay) == 0):
                self.pause = False
                self.audioTime = time.time() - self.timeStart
                self.timeStart = 0
            elif (self.timeStop > 0 or self.wrongKeys > 5):
                self.playerStuck = True           
        elif (not self.animationStop):
            self.executeAndUpdateCommand()
            self.growOrDropAllTiles()
            self.checkHitBottom()
            self.removeTile()

    def drawTiles(self, canvas):
        for tile in self.tiles:
            tile.draw(canvas)

    def drawKeyboard(self, canvas):
        self.keyboard.drawWhiteKeys(canvas)
        self.keyboard.drawBlackKeys(canvas)
        self.keyboard.drawKeyNotations(canvas)

    def drawInstructions(self, canvas):
        keysToPlay = list(aubio.midi2note(midi) for midi in self.keysToPlay)
        keysToPlay = ', '.join(keysToPlay)
        canvas.create_text(50, 50, text='Keys to play: ' + keysToPlay,
                           font='Avenir 20 bold', fill='white', anchor='w')
        
        if (self.keyboard.wrongKeyPressed == 0):
            wrongKeyPlayed = ''
        else:
            wrongKeyPlayed = aubio.midi2note(self.keyboard.wrongKeyPressed)
        keyPlayed = f'You played: {wrongKeyPlayed}'
        canvas.create_text(50, 100, text=keyPlayed,
                           font='Avenir 20 bold', fill='white', anchor='w')
        keysBeingPlayed = list(aubio.midi2note(midi) for midi in self.keysBeingPlayed)
        keysBeingPlayed = ', '.join(keysBeingPlayed)
        canvas.create_text(50, 150, text='Keys being played: ' + keysBeingPlayed,
                           font='Avenir 20 bold', fill='white', anchor='w')
        canvas.create_text(self.width - 50, 50, text=f'Nonstop mode: {self.nonStop}',
                           font='Avenir 20 bold', fill='white', anchor='e')
        canvas.create_text(self.width - 50, 100, text=f'Key#: {self.numberOfKeysPlayed}',
                           font='Avenir 20 bold', fill='white', anchor='e')

    def askIfPlayerStuck(self, canvas):
        if (self.playerStuck):
            text = 'Are you stucked? "s" to skip and "k" to keep playing'
            width, height = 230, 20
            canvas.create_rectangle(self.width / 2 - width, 50 - height,
                                    self.width / 2 + width, 50 + height,
                                    fill='red')
            canvas.create_text(self.width / 2, 50, text=text,
                               fill='white', font='Avenir 18 bold')
        
    def drawErrorMessage(self, canvas):
        if (self.printErrorMessage):
            width, height = 120, 20
            canvas.create_rectangle(self.width / 2 - width, 50 - height,
                                    self.width / 2 + width, 50 + height,
                                    fill='red')
            canvas.create_text(self.width / 2, 50, text='No such file in directory!',
                            fill='white', font='Avenir 18 bold')
        
    def redrawAll(self, canvas):
        canvas.create_rectangle(0,0,self.width, self.height, fill='black')
        self.drawTiles(canvas)
        self.drawKeyboard(canvas)
        self.drawInstructions(canvas)
        self.askIfPlayerStuck(canvas)
        self.drawErrorMessage(canvas)

class ComposeMode(Mode):
    works = dict() # save the player's own work here
    def appStarted(self):
        self.setUpBasicInfo()
        self.setUpKeyboard()
        self.setUpStream()
    
    def setUpBasicInfo(self):
        # for compose
        self.askForConfirmation = True
        self.playBackMode = False
        self.timerOn = False
        self.recordingNote = False
        self.recordingLength = False
        self.keyStart = False
        self.keyLength = None
        self.timeElapsed = 0 # time elapsed in progress
        self.delay = 0 # total time elapsed
        self.commandsGenerated = [ ]
        self.keysPlayed = [ ]
        self.keysGenerated = [ ]
        self.memory = None # very limited memory
        # for playback
        self.resetTimer()
        self.printErrorMessage = False
        self.animationStop = True
        self.currentCommands = [ ] # put here to avoid crashing
        self.tiles = [ ]
        self.keysToPlay = [ ] # in midi
        self.keysBeingPlayed = [ ]

    def setUpKeyboard(self):
        self.keyboard = Keyboard(self.width, self.height)
        ComposeMode.midiToPositions = self.keyboard.midiToPositions

    def setUpStream(self):
        self.stream = Stream()

    def keyPressed(self, event):
        if (event.key == 'h'):
            self.app.setActiveMode(self.app.composeHelpMode)
        elif (not self.playBackMode):
            if (event.key == 's'):
                self.startRecordingNote()
            elif (event.key == 'Space'):
                self.insertEmptyNotes()
                if (self.delay == 0):
                    self.memorize()
            elif (event.key == 'y'
                  and self.askForConfirmation and self.keysPlayed != [ ]):
                self.startToRecordLength()
                if (self.delay == 0):
                    self.memorize()
            elif (event.key == 'n' and self.askForConfirmation):
                if (self.keysPlayed != [ ] and self.delay == 0): # hasnt specify key
                    self.deleteOneKey()
                elif (self.delay != 0):
                    self.clearTime()
            elif (event.key == 'd'
                  and self.askForConfirmation):
                self.detachKey()
            elif (event.key == 'Enter'): # Done composing
                self.saveFile()
            elif (event.key == 'q'):
                self.app.setActiveMode(self.app.splashScreenMode)
            elif (event.key == 'r'):
                self.appStarted() # just do this all over again
            elif (event.key == 'p'): # playback mode
                self.playBackMode = True
                self.getCommands()
        else:
            if (event.key == 'p'):
                self.playBackMode = False
            elif (event.key == 'Space'):
                self.animationStop = not self.animationStop
            elif (event.key == 'r'):
                self.getCommands()

    def resetTimer(self):
        self.startTime = time.time()

    def getCommands(self):
        self.commands = self.commandsGenerated
        self.commandIndex = 0
        self.currentCommands = self.getNewCommand()

    def addAndEditTiles(self, command):
        midi, press, delay = command
        if (press):
            newTile = ComposedTile(midi, self.keyboard.keyTop)
            self.tiles.append(newTile)
        else:
            for tile in self.tiles:
                if (tile.midi == midi):
                    tile.isGrowing = False

    def getNewCommand(self):
        if (self.commandIndex == len(self.commands)): return [ ]
        end = self.commandIndex + 1
        while (end < len(self.commands) and self.commands[end][2] == 0):
            end += 1
        commands = self.commands[self.commandIndex : end]
        self.commandIndex = end
        return commands

    def executeAndUpdateCommand(self):
        if (self.currentCommands == [ ]): return
        timeElapsed = time.time() - self.startTime
        if (timeElapsed > self.currentCommands[0][2]):
            for command in self.currentCommands:
                self.addAndEditTiles(command)
            self.currentCommands = self.getNewCommand()
            self.resetTimer()

    def growOrDropAllTiles(self):
        for tile in self.tiles:
            tile.growOrMove()

    def removeTile(self):
        temp = copy.deepcopy(self.tiles)
        for key in self.tiles:
            if (key.y1 < 0):
                temp.remove(key)
        self.tiles = temp

    def startRecordingNote(self):
        self.recordingNote = True
        self.askForConfirmation = False

    # this can also be used as a shortcut to specify length
    def insertEmptyNotes(self):
        self.keyStart = not self.keyStart
        if (self.keyStart):
            self.keyStartTime = time.time()
            self.askForConfirmation = False
            self.timerOn = True
        else:
            self.delay += self.timeElapsed
            self.askForConfirmation = True
            self.timerOn = False

    def startToRecordLength(self):
        self.recordingLength = True
        self.askForConfirmation = False

    def deleteOneKey(self):
        key = self.keysPlayed.pop()
        self.commandsGenerated.pop()
        self.keyboard.releaseKey(key.midi)
    
    def memorize(self):
        keysPlayed = copy.deepcopy(self.keysPlayed)
        keysGenerated = copy.deepcopy(self.keysGenerated)
        self.memory = (keysPlayed, keysGenerated)

    def clearTime(self):
        self.delay = 0
        keysPlayed, keysGenerated = self.memory
        self.keysPlayed, self.keysGenerated = keysPlayed, keysGenerated

    def saveFile(self):
        name = self.getUserInput('Enter name for your work:')
        ComposeMode.works[name] = self.commandsGenerated
        with open(f'{name}.txt', 'w') as filehandle: # learn from 
            filehandle.writelines(f'{str(command)}\n' for command in self.commandsGenerated)

    def timer(self):
        if (not self.timerOn): return
        self.timeElapsed = time.time() - self.keyStartTime

    def detachKey(self):
        for key in self.keysPlayed:
            if (key.color == 'pink'): # those selected by the player to detach
                self.keysPlayed.remove(key)
                key.isGrowing = False
                key.color = 'yellow'
                self.commandsGenerated.append((key.midi, 0, self.delay))
                self.keyboard.releaseKey(key.midi)
                self.keysGenerated.append(key)
        #self.detachMode = False
        self.delay = 0

    def mousePressed(self, event):
        for key in self.keysPlayed:
            if (key.clicked(event.x, event.y)):
                key.color = 'pink'

    def confirmNote(self):
        if (not self.recordingNote): return
        self.stream.openStream()
        keyPlayed = self.stream.getKeyPlayed(3, 5)
        self.stream.closeStream()
        if (keyPlayed != 0): # didnt play something after 5 seconds
            self.keysPlayed.append(ComposedTile(keyPlayed, self.keyboard.keyTop))
            self.keyboard.pressKey(keyPlayed)
            self.commandsGenerated.append((keyPlayed, 64, self.delay))
        self.delay = 0
        self.recordingNote = False # one note at a time
        self.askForConfirmation = True

    def recordLength(self):
        if (self.recordingLength):
            self.stream.openStream()
            keysPlayed = list(key.midi for key in self.keysPlayed)
            # Start recording
            if (not self.keyStart and self.stream.targetNoteBeingPlayed(keysPlayed)):
                self.keyStartTime = time.time()
                self.keyStart = True
                self.timerOn = True
            # Done recording
            elif (self.keyStart and not self.stream.targetNoteBeingPlayed(keysPlayed)):
                self.delay += self.timeElapsed
                self.keyStart = False
                self.recordingLength = False
                self.askForConfirmation = True
                self.timerOn = False

    def generateKey(self):
        if (not self.keyStart): return
        for key in self.keysPlayed:
            key.growOrMove()
        for key in self.keysGenerated:
            key.growOrMove()

    def removeKey(self):
        for key in self.keysGenerated:
            if (key.y1 < 0):
                self.keysGenerated.remove(key)
                #print(self.keysGenerated)
                break

    def timerFired(self):
        if  (not self.playBackMode):
            self.confirmNote()
            self.recordLength()
            self.generateKey()
            self.removeKey()
            self.timer()
        elif (not self.animationStop):
            self.executeAndUpdateCommand()
            self.growOrDropAllTiles()
            self.removeTile()

    def drawTiles(self, canvas):
        if (not self.playBackMode):
            for key in self.keysPlayed:
                key.draw(canvas)
            for key in self.keysGenerated:
                key.draw(canvas)
        else:
            for tile in self.tiles:
                tile.draw(canvas)

    def drawKeyboard(self, canvas):
        self.keyboard.drawWhiteKeys(canvas)
        self.keyboard.drawBlackKeys(canvas)
        self.keyboard.drawKeyNotations(canvas)

    def drawInstructions(self, canvas):
        keysPlayed = list(aubio.midi2note(key.midi) for key in self.keysPlayed)
        keysPlayed = ', '.join(keysPlayed)
        canvas.create_text(50, 50, text='You played: ' + keysPlayed,
                           font='Avenir 20 bold', fill='white', anchor='w')
        keysGenerated = list(aubio.midi2note(key.midi) for key in self.keysGenerated)
        keysGenerated = ', '.join(keysGenerated)
        canvas.create_text(50, 100, text='Keys generated: ' + keysGenerated,
                           font='Avenir 20 bold', fill='white', anchor='w')
        canvas.create_text(self.width - 50, 50, text='Time elapsed: %0.2f seconds' % self.timeElapsed,
                           font='Avenir 20 bold', fill='white', anchor='e')

    def drawRecording(self, canvas):
        text = 'Recording...' if (self.recordingNote) else 'Awaiting...'
        canvas.create_text(self.width / 2, 50, text=text, fill='white', font='Avenir 20 bold')

    # this is like an advanced help mode
    def askIfContinue(self, canvas):
        if (not self.askForConfirmation): return
        if (self.keysPlayed != [ ] and self.timeElapsed == 0):
            text = 'Press "y" to start specify the length if that is all the keys you want to play.'
            canvas.create_text(self.width / 2, 100, text=text, fill='white', font='Avenir 14')
            text2 = 'Or press "n" to undo the last note you created.'
            canvas.create_text(self.width / 2, 120, text=text2, fill='white', font='Avenir 14')
        elif (self.timeElapsed != 0 and self.keysPlayed != [ ]):
            text1 = 'You just played the keys for %0.2f seconds.' % self.delay
            canvas.create_text(self.width / 2, 100, text=text1, fill='white', font='Avenir 14')
            text2 = 'Press "y" to continue, "n" to clear, or click the note you are done with and press "d".'
            canvas.create_text(self.width / 2, 120, text=text2, fill='white', font='Avenir 14')
        elif (self.delay != 0 and self.keysPlayed == [ ]): # empty note
            text1 = 'You just played the empty key for %0.2f seconds.' % self.delay
            canvas.create_text(self.width / 2, 100, text=text1, fill='white', font='Avenir 14')
            text2 = 'Press "Space" to continue, "n" to clear, or "s" to insert a note.'
            canvas.create_text(self.width / 2, 120, text=text2, fill='white', font='Avenir 14')
        else:
            text = 'Press "s" to insert a note or "Space" to record empty note.'
            canvas.create_text(self.width / 2, 100, text=text, fill='white', font='Avenir 14')

    def drawTestingText(self, canvas):
        canvas.create_text(50, 150, text='KeyStart: ' + str(self.keyStart),
                           font='Avenir 20 bold', fill='white', anchor='w')
        canvas.create_text(50, 200, text=f'RecordingLength: {self.recordingLength}',
                           font='Avenir 20 bold', fill='white', anchor='w')
        canvas.create_text(50, 250, text=f'Commands: {self.commandsGenerated}',
                           font='Avenir 20 bold', fill='white', anchor='w')

    def drawPlayBackModeThing(self, canvas):
        canvas.create_text(self.width / 2, 50, text='Playing back...', fill='white', font='Avenir 20 bold')
        canvas.create_text(self.width / 2, 100, text=f'Current commands: {self.currentCommands}',
                           fill='white', font='Avenir 14 bold')
    
    def redrawAll(self, canvas):
        canvas.create_rectangle(0,0,self.width, self.height, fill='black')
        self.drawTiles(canvas)
        self.drawKeyboard(canvas)
        if (not self.playBackMode):
            self.drawInstructions(canvas)
            self.drawRecording(canvas)
            self.askIfContinue(canvas)
            # self.drawTestingText(canvas)
        else:
            self.drawPlayBackModeThing(canvas)

class SplashScreenMode(Mode):
    def appStarted(self):
        self.cx = self.app.width / 2
        self.cy = self.app.height / 2
        self.showIntro = False
        self.addButtons()
        self.fillScreenWithBackground()
       
    def addButtons(self):
        cx, width, height = self.width / 2, 70, 30
        self.buttons = [ ]
        self.buttons.append(Button(cx, self.height / 2 + 10, width, height, 'Practice'))
        self.buttons.append(Button(cx, self.height / 2 + 110, width, height, 'Compose'))
    
    # resize the background picture to fit the screen and specify the moving speed
    def loadBackground(self):
        self.backgroundImage = self.loadImage('background5.jpg')
        self.backgroundWidth, self.backgroundHeight = self.backgroundImage.size
        self.resizeRatio = (self.app.height + 5) / self.backgroundHeight
        self.backgroundImage = self.scaleImage(self.backgroundImage, self.resizeRatio)
        self.backgroundWidth, self.backgroundHeight = self.backgroundImage.size
        self.backgroundSpeed = 1

    # to create a infinitely moving background, we need to draw more than one image at a time
    def fillScreenWithBackground(self):
        self.loadBackground()
        self.background3 = Background(5 * self.backgroundWidth / 2, -2 * self.backgroundWidth)
        self.background2 = Background(5 * self.backgroundWidth / 2, -self.backgroundWidth)
        self.background1 = Background(5 * self.backgroundWidth / 2, 0)
    
    def mousePressed(self, event):
        buttonClicked = None
        for button in self.buttons:
            if (button.clicked(event.x, event.y)):
                buttonClicked = button.text
        if (buttonClicked == 'Practice'):
            self.app.setActiveMode(self.app.practiceMode)
        elif (buttonClicked == 'Compose'):
            self.app.setActiveMode(self.app.composeMode)

    def keyPressed(self, event):
        if (event.key == 'h'):
            self.app.setActiveMode(self.app.generalHelpMode)

    def timerFired(self):
        self.background1.scrollX += self.backgroundSpeed
        self.background2.scrollX += self.backgroundSpeed
        self.background3.scrollX += self.backgroundSpeed

    def drawButtons(self, canvas):
        for button in self.buttons:
            button.draw(canvas)

    def drawTitle(self, canvas):
        canvas.create_text(self.width / 2, 120, text='Piano Tile',
                           fill='white', font='SnellRoundhand 80 bold')

    def drawInfo(self, canvas):
        text = 'Practice, create, and more... Press "h" for help'
        canvas.create_text(20, self.height - 20, text=text,
                           fill='white', font='SnellRoundhand 12', anchor='w')

    def drawBackground1(self, canvas):
        sx = self.background1.scrollX % (3 * self.backgroundWidth)
        canvas.create_image(self.background1.cx - sx, self.cy, image=ImageTk.PhotoImage(self.backgroundImage))

    def drawBackground2(self, canvas):
        sx = self.background2.scrollX % (3 * self.backgroundWidth)
        canvas.create_image(self.background2.cx - sx, self.cy, image=ImageTk.PhotoImage(self.backgroundImage))

    def drawBackground3(self, canvas):
        sx = self.background3.scrollX % (3 * self.backgroundWidth)
        canvas.create_image(self.background3.cx - sx, self.cy, image=ImageTk.PhotoImage(self.backgroundImage))

    def redrawAll(self, canvas):
        #canvas.create_rectangle(0,0,self.width, self.height, fill='black')
        self.drawBackground1(canvas)
        self.drawBackground2(canvas)
        self.drawBackground3(canvas)
        self.drawTitle(canvas)
        self.drawInfo(canvas)
        self.drawButtons(canvas)

class GeneralHelpMode(Mode):
    def redrawAll(self, canvas):
        font = 'TigerExpert 14'
        text = '''\
To users,

Welcome to this Piano Tile App. If you simply want to play some piano recreationally or even compose some music on your own, this is the app for you!
With the help of this app, you actually don't need to know how to read a stave in order to play a piece of beautiful music. But of course, it is very
essential that you have such knowledge if you are actually serious about music.

For practice mode, you can import any MIDI file you find on the internet into this app. To do this, you simply download the file and put it in to the
same folder with the app, which is provided for you along with the code. Then, the app will generate a piano tile animation for you to play with.
You can either use the practice mode to help you find the correct note to play or the right tempo to play. Or if you don't have an instrument to play
with, you can just directly sing to your computer and the app will also be able to identify your pitch.

For compose mode, you can just play your instrument to your computer, and then the app will generate the corresponding animation for you. You can
save it in this app, and it will also save it as a txt. file into your directory. What's more, you can play back your own saved creation in practice
mode if you want to. The mode is very straightforward to use compared to those professional editors, but it is also, naturally, less complex. Again,
this app is mainly dedicated to recreational purposes.

The most wonderful thing about this app is that you don't need any external devices to do all these things: it simply use your computer's built-in
microphone to detect sound. And this app also works with instruments other than piano!

Hope you enjoy!
'''
        canvas.create_rectangle(0, 0, self.width, self.height, fill='black')
        canvas.create_text(self.width / 2, self.height / 2, text=text, font=font, fill='white')
        #canvas.create_text(self.width/2, self.height - 20, text='Press "h" to return', font=font, fill='white')

    def keyPressed(self, event):
        self.app.setActiveMode(self.app.splashScreenMode)

class PracticeHelpMode(Mode):
    def redrawAll(self, canvas):
        font = 'TigerExpert 16'
        text = '''\
Non-stop mode can be used either when you are pretty proficient in playing the piece
and want to use the animation to calibrate your tempo, or if you simply want to get 
a broad sense how the piece looks like.

"n"     ->  To switch on/off non-stop mode
"Space" ->  To pause/unpause animation in non-stop mode
"s"     ->  To skip the key when stucked
"k"     ->  To keep playing when stucked
"p"     ->  Get your feedback plot after finish a piece
"q"     ->  Quit to splash screen
"r"     ->  Restart the mode, re-enter the file path
'''
        canvas.create_rectangle(0, 0, self.width, self.height, fill='black')
        canvas.create_text(self.width / 2, self.height / 2, text=text, font=font, fill='white')

    def keyPressed(self, event):
        self.app.setActiveMode(self.app.practiceMode)

class ComposeHelpMode(Mode):
    def redrawAll(self, canvas):
        font = 'TigerExpert 16'
        text = '''\
Play-back mode allows you to check your own progress without switching modes, it plays back
your creation up to that point so that you can see what haveyou created so far before
continuing, so that you can have a clear idea of the whole thing.

"p"     ->  To switch on/off play-back mode

Play-back Mode:
"Space" ->  To pause/unpause animation in play-back mode
"r"     ->  Restart the play-back mode (play again from the beginning)

Compose Mode:
"s"     ->  Opens up the stream to get notes to play
"Space" ->  Insert empty notes
"y"     ->  Start specify the length of the note
"n"     ->  A general undo button
"d"     ->  Detach the key once finish recording
"Enter" ->  Save your work to the app and computer
"q"     ->  Quit to splash screen
"r"     ->  Restart the mode, wipe out current progress

Just follow the on-screen instruction, you got this!
'''
        canvas.create_rectangle(0, 0, self.width, self.height, fill='black')
        canvas.create_text(self.width / 2, self.height / 2, text=text, font=font, fill='white')

    def keyPressed(self, event):
        self.app.setActiveMode(self.app.composeMode)

class PianoTile(ModalApp):
    def appStarted(app):
        app.splashScreenMode = SplashScreenMode()
        app.generalHelpMode = GeneralHelpMode()
        app.practiceHelpMode = PracticeHelpMode()
        app.composeHelpMode = ComposeHelpMode()
        app.practiceMode = PracticeMode()
        app.composeMode = ComposeMode()
        app.setActiveMode(app.splashScreenMode)
        app.timerDelay = 1

PianoTile(width=1200, height=500)