Project Description:

Welcome to this Piano Tile App. If you simply want to play some piano recreationally or even compose some music on your own, this is the app for you! With the help of this app, you actually don't need to know how to read a stave in order to play a piece of beautiful music. But of course, it is very essential that you have such knowledge if you are actually serious about music.

For practice mode, you can import any MIDI file you find on the internet into this app. To do this, you simply download the file and put it in to the same folder with the app, which is provided for you along with the code. Then, the app will generate a piano tile animation for you to play with. You can either use the practice mode to help you find the correct note or the tempo to play. Or if you don't have an instrument to play with, you can just directly sing to your computer and the app will also be able to identify your pitch.

For compose mode, you can just play your instrument to your computer, and then the app will generate the corresponding animation for you. You can save it in this app, and it will also save it as a txt. file into your directory. What's more, you can play back your own saved creation in practice mode if you want to. The mode is very straightforward to use compared to those professional editors, but it is also, naturally, less complex. Again, this app is mainly dedicated to recreational purposes.


How To Run:

1. Create a folder on your computer, or just use the given app folder.
2. The app file is named "allMyPreciousWork.py". So put this file into what ever folder you created
3. Put "cmu_112_graphics.py" in to the folder. This is the framework provided by the wonderful people of CMU 15-112-F19. I couldn't have achieved anything without them.
4.Put "background5.jpg" into the folder. This is the background picture of the splash screen.
5. There are four demo MIDI files provided for you. If there is any other file you want to import, put them in this folder.
6. Open the app file and run it. Enjoy


Modules Used:

from cmu_112_graphics import *	(112 exclusive!)
import time, copy		(built-in)
from tkinter import * 		(built-in)
from PIL import Image
import matplotlib.pyplot as plt
import mido
import pyaudio
import numpy as np
import aubio


Shortcut Commands:

Not really. The function of this app is pretty specific: it is a auxiliary tool for people who would like to play music. So, if you were ever to run this app, it would be ideal if you have an instrument in front of you (preferably a piano), and an MIDI file of the script you want to play downloaded.

The following commands will allow you to test out this program without an instrument:

	1. In practice mode, turn on non-stop mode so that the stream is deactivated and will not freeze the program. Then, you can simply press "Space" to pause/unpause the animation
	2. In compose mode, instead of specifying the length of the key by playing the actual instrument, do it by simply pressing "Space" as when you are inserting the empty notes.

If any of these doesn't make sense, refer to the built-in help mode by simply pressing "h" under any mode.
