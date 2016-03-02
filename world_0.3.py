import sys
import time

import rospy
# import servo
from beginner.msg import MsgFlystate
from direct.gui.OnscreenText import OnscreenText
from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from panda3d.core import AmbientLight, DirectionalLight, Vec4, Vec3, Fog, LVecBase3f
from panda3d.core import loadPrcFileData, NodePath
from pandac.PandaModules import CompassEffect
import subprocess, rostopic
import matplotlib.pyplot as plt
from matplotlib.path import Path
import matplotlib.patches as patches
import numpy as np

try:
    # Checkif rosmaster is running or not.
    rostopic.get_topic_class('/rosout')
    is_rosmaster_running = True
except rostopic.ROSTopicIOException as e:
    roscore = subprocess.Popen('roscore')  # then start roscore yourself
    time.sleep(1)  # wait a bit to be sure the roscore is really launched
    subprocess.Popen(["roslaunch", "Kinefly", "main.launch"])
    # os.system("roslaunch Kinefly main.launch")
    # time.sleep(1)

size = 257
pos = ori = []

print "pos is ", pos


class MyApp(ShowBase):
    def __init__(self):
        global treePos, redPos, prevPos, ax, fig
        loadPrcFileData("", "win-size 2720 768")  # set window size
        ShowBase.__init__(self)  # start the app
        rospy.init_node('apple')  # init node
        self.debug = False  # deubbing, prints pos
        self.statusLabel = self.makeStatusLabel(0)

        # Constatns

        # booleans
        self.loadSpheres = True  # False
        self.loadTree = True  # False
        self.loadWind = True

        # params
        self.worldSize = size  # relevant for world boundaries
        self.initPos = LVecBase3f(self.worldSize / 2, 90, 1.3)  # z is factored by 2 dunno why?
        self.initH = 0
        prevPos = (self.initPos[0], self.initPos[1])
        treePos = Vec3(self.worldSize / 2 + 20, self.worldSize / 2, 1)
        redPos = Vec3(self.worldSize / 2 - 20, self.worldSize / 2, 1.8)
        self.speed = 0.0
        self.maxspeed = 25.0
        self.speedIncrement = 0.1

        self.closedGain = 1  # gain for turning

        self.maxdistance = 200
        self.camLens.setFar(self.maxdistance)
        self.camLens.setFov(120)

        # load up the models
        # world
        self.world = self.loader.loadModel("models/world" + str(size) + ".bam")  # loads the world of dimesions size
        self.world.reparentTo(self.render)  # render the world

        # the Player
        self.player = NodePath("player")
        self.player.setPos(self.world, self.initPos)
        self.player.setH(self.world, self.initH)  # heading angle is 0

        # sphere
        # load model, set position, set scale, apply texture
        self.spherePath = "models/sphere.egg"

        if self.loadSpheres:
            # Red sphere
            self.redSphere = self.loader.loadModel("models/sphere.egg")
            self.redSphere.setPos(self.world, redPos)
            self.redSphere.setScale(0.4)
            # load redSphere texture
            self.redTex = self.loader.loadTexture("models/red.tga")
            self.redSphere.setTexture(self.redTex)
            self.redSphere.reparentTo(self.render)

            # Green Sphere
            self.greenSphere = self.loader.loadModel("models/sphere.egg")
            self.greenSphere.setPos(self.world, self.worldSize / 2 - 20, self.worldSize / 2, 1.8)
            self.greenSphere.setScale(0.4)
            # load greenSphere texture
            self.greenTex = self.loader.loadTexture("models/green.tga")
            self.greenSphere.setTexture(self.greenTex)
            # self.greenSphere.reparentTo(self.render)

        # Load tree

        if self.loadTree:
            self.tree = self.loader.loadModel("models/treeHighB.egg")
            self.tree.setPos(self.world, treePos)
            self.tree.setScale(0.03)

            self.treeTex = self.loader.loadTexture("models/BarkBrown.tga")
            self.tree.setTexture(self.treeTex)
            self.tree.reparentTo(self.render)

        # function calls
        # wbad
        self.wbad = self.wbas = 0
        self.listener()
        # A task to run every frame, some keyboard setup and our speed
        self.taskMgr.add(self.updateTask, "update")
        self.keyboardSetup()
        self.createEnvironment()

        fig = plt.figure()
        self.trajectory()
        self.frameNum = 0

        # self.i

    def trajectory(self):

        global ax
        ax=fig.add_subplot(111)
        ax.set_xlim(0,size)
        ax.set_ylim(0,size)
        plt.plot(treePos[0],treePos[1],'gs')
        plt.plot(redPos[0],redPos[1],'ro')
        plt.ion()
        plt.show()
        # # global pos, ori
        # # pos.append(self.player.getPos(self.world))
        # # ori.append(self.player.getHpr(self.world))
        # # # print "pos is ",pos
        # # print "ori is ",ori

    def windTunnel(self, windDirection):
        self.servoAngle = (self.player.getH() % 360) - 180

    def modelLoader(self, modelName, modelPath, modelPos, modelScale, texName, texPath, modelParent):
        modelName = self.loader.loadModel(modelPath)
        modelName.setPos(modelParent, modelPos)
        modelName.setScale(modelScale)

        texName = self.loader.loadTexture(texPath)
        modelName.setTexture(texName)
        modelName.reparentTo(self.render)

    def callback(self, data):
        """ Returns Wing Beat Amplitude Difference from received data"""
        self.wbad = data.left.angles[0] - data.right.angles[0]
        self.wbas = data.left.angles[0] + data.right.angles[0]
        return self.wbad

    def listener(self):
        """ Listens to Kinefly Flystate topic"""
        rospy.Subscriber("/kinefly/flystate", MsgFlystate, self.callback)

        # print self.wbad

    def makeStatusLabel(self, i):
        return OnscreenText(style=2, fg=(0.5, 1, .5, 1), pos=(-1.3, 0.92 - (.08 * i)), mayChange=1)

    def keyboardSetup(self):
        self.keyMap = {"left": 0, "right": 0, "climb": 0, "fall": 0, \
                       "accelerate": 0, "decelerate": 0, "handBrake": 0, "reverse": 0,
                       "closed": 0, "init": 0, "gain-up": 0, "gain-down": 0,
                       "newInit": 0, "clf": 0}
        self.accept("escape", sys.exit)
        self.accept("a", self.setKey, ["climb", 1])
        self.accept("a-up", self.setKey, ["climb", 0])
        self.accept("z", self.setKey, ["fall", 1])
        self.accept("z-up", self.setKey, ["fall", 0])
        self.accept("arrow_left", self.setKey, ["left", 1])
        self.accept("arrow_left-up", self.setKey, ["left", 0])
        self.accept("arrow_right", self.setKey, ["right", 1])
        self.accept("arrow_right-up", self.setKey, ["right", 0])
        self.accept("arrow_down", self.setKey, ["decelerate", 1])
        self.accept("arrow_down-up", self.setKey, ["decelerate", 0])
        self.accept("arrow_up", self.setKey, ["accelerate", 1])
        self.accept("arrow_up-up", self.setKey, ["accelerate", 0])
        self.accept("o", self.setKey, ["closed", 0])
        self.accept("p", self.setKey, ["closed", 1])
        self.accept("r", self.setKey, ["reverse", 1])
        self.accept("r-up", self.setKey, ["reverse", 0])
        self.accept("s", self.setKey, ["handBrake", 1])
        self.accept("s-up", self.setKey, ["handBrake", 0])
        self.accept("i", self.setKey, ["init", 1])
        self.accept("i-up", self.setKey, ["init", 0])
        self.accept("u", self.setKey, ["gain-up", 1])
        self.accept("u-up", self.setKey, ["gain-up", 0])
        self.accept("y", self.setKey, ["gain-down", 1])
        self.accept("y-up", self.setKey, ["gain-down", 0])
        self.accept("]", self.setKey, ["newInit", 1])
        self.accept("]-up", self.setKey, ["newInit", 0])
        self.accept("q", self.setKey, ["clf", 1])
        self.accept("q-up", self.setKey, ["clf", 0])
        base.disableMouse()  # or updateCamera will fail!

    def createEnvironment(self):
        # Fog to hide a performance tweak:
        colour = (0.0, 0.0, 0.0)
        expfog = Fog("scene-wide-fog")
        expfog.setColor(*colour)
        expfog.setExpDensity(0.004)
        render.setFog(expfog)
        base.setBackgroundColor(*colour)

        # Our sky
        skysphere = loader.loadModel('models/sky.egg')
        skysphere.setEffect(CompassEffect.make(self.render))
        skysphere.setScale(self.maxdistance / 2)  # bit less than "far"
        skysphere.setZ(-5)
        # NOT render - you'll fly through the sky!:
        skysphere.reparentTo(self.camera)

        # Our lighting
        ambientLight = AmbientLight("ambientLight")
        ambientLight.setColor(Vec4(.6, .6, .6, 1))
        directionalLight = DirectionalLight("directionalLight")
        directionalLight.setDirection(Vec3(0, -10, -10))
        directionalLight.setColor(Vec4(1, 1, 1, 1))
        directionalLight.setSpecularColor(Vec4(1, 1, 1, 1))
        render.setLight(render.attachNewNode(ambientLight))
        render.setLight(render.attachNewNode(directionalLight))

    def setKey(self, key, value):
        self.keyMap[key] = value

    def updateTask(self, task):
        self.updatePlayer()
        self.updateCamera()
        return Task.cont

    def updatePlayer(self):
        global prevPos, currentPos, ax, fig, treePos, redPos
        # Global Clock
        # by default, panda runs as fast as it can frame to frame
        scalefactor = self.speed * 1 / 250  # (globalClock.getDt()*self.speed)
        climbfactor = (.01) + scalefactor * 1
        bankfactor = .5  # (.4) + scalefactor * 6.5
        speedfactor = scalefactor * 1

        self.frameNum+=1
        if (self.frameNum%30==1):

            currentPos=(self.player.getX(),self.player.getY())
            verts=[(prevPos),(currentPos)]
            codes=[Path.MOVETO,Path.LINETO]
            path=Path(verts,codes)

            patch=patches.PathPatch(path,facecolor='white',lw=2)#,color=hex(self.frameNum))
            ax.add_patch(patch)
            fig.canvas.draw()
            fig.canvas.flush_events()
            prevPos=currentPos



        if (self.keyMap["clf"] != 0):
            plt.clf()
            self.trajectory()

        # print self.wbad

        # closed loop
        if (self.keyMap["closed"] != 0):
            self.player.setH(self.player.getH() - self.wbad * self.closedGain)

        # Climb and Fall
        if (self.keyMap["climb"] != 0):  # and self.speed > 0.00):
            # faster you go, quicker you climb
            self.player.setZ(self.player.getZ() + climbfactor)

        elif (self.keyMap["fall"] != 0):  # and self.speed > 0.00):
            self.player.setZ(self.player.getZ() - climbfactor)

        # Left and Right
        if (self.keyMap["left"] != 0):  # and self.speed > 0.0):
            self.player.setH(self.player.getH() + bankfactor)
        elif (self.keyMap["right"] != 0):  # and self.speed > 0.0):
            self.player.setH(self.player.getH() - bankfactor)

        # throttle control
        if (self.keyMap["accelerate"] != 0):
            self.speed += self.speedIncrement
            if (self.speed > self.maxspeed):
                self.speed = self.maxspeed
        elif (self.keyMap["decelerate"] != 0):
            self.speed -= self.speedIncrement
            if (self.speed < 0.0):
                self.speed = 0.0
        # handbrake
        if (self.keyMap["handBrake"] != 0):
            self.speed = 0

        # reverse gear
        if (self.keyMap["reverse"] != 0):
            self.speed -= self.speedIncrement

        # move forwards
        self.player.setY(self.player, speedfactor)

        # respect max camera distance else you
        # cannot see the floor post loop the loop!
        if (self.player.getZ() > self.maxdistance):
            self.player.setZ(self.maxdistance)

        elif (self.player.getZ() < 0.5):
            self.player.setZ(0.5)

        # and now the X/Y world boundaries:
        if (self.player.getX() < 0):
            self.player.setX(0)
        elif (self.player.getX() > self.worldSize):
            self.player.setX(self.worldSize)

        if (self.player.getY() < 0):
            self.player.setY(0)
        elif (self.player.getY() > self.worldSize):
            self.player.setY(self.worldSize)

        # reset to initial position
        if (self.keyMap["init"] != 0):
            self.player.setPos(self.world, self.initPos)
            self.player.setH(self.initH)

        if (self.keyMap["newInit"] != 0):
            self.initPos = self.player.getPos(self.world)
            self.initH = self.player.getH(self.world)
            print "new init pos is ", self.initPos
            print "new init H is ", self.initH
        # update gain
        self.gainIncrement = 0.005
        if (self.keyMap["gain-up"] != 0):
            self.closedGain += self.gainIncrement
            print "gain is", self.closedGain
        elif (self.keyMap["gain-down"] != 0):
            self.closedGain -= self.gainIncrement

            print "gain is ", self.closedGain

    def updateCamera(self):
        # see issue content for how we calculated these:
        self.camera.setPos(self.player, 0, 0, 0)  # 25.6225, 3.8807, 10.2779)
        self.camera.setHpr(self.player, 0, 0, 0)  # 94.8996,-16.6549,1.55508)
        if self.debug:
            print "POS" + str(self.player.getPos(self.world))
            print "HPR" + str(self.player.getHpr(self.world))
app = MyApp()
app.run()
