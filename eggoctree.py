
#!/usr/bin/python
"""
                             _                 
                            | |               
  ___  __ _  __ _  ___   ___| |_ _ __ ___  ___
 / _ \/ _` |/ _` |/ _ \ / __| __| '__/ _ \/ _ \
|  __/ (_| | (_| | (_) | (__| |_| | |  __/  __/
 \___|\__, |\__, |\___/ \___|\__|_|  \___|\___|
       __/ | __/ | by treeform                           
      |___/ |___/                                                             
                             
This is a replacement of raytaller wonderful
Egg Octree script many people had problem using it
( i always guessed wrong about the size of cells )
and it generated many "empty" branches which this
one does not. 
original see : ( http://panda3d.org/phpbb2/viewtopic.php?t=2502 )
This script like the original also released under the WTFPL license.
Usage: egg-octreefy [args] [-o outfile.egg] infile.egg [infile.egg...] 
-h     display this
-v     verbose
-l     list resulting egg file
-n     number of triangles per leaf (default 3)
if outfile is not specified "infile"-octree.egg assumed
"""
import sys, getopt
import math
from pandac.PandaModules import *
global verbose,listResultingEgg,maxNumber
listResultingEgg = False
verbose = False
maxNumber = 3
   
def getCenter(vertexList):
    """ get a list of Polywraps and figure out their center """
    # Loop on the vertices determine the bounding box
    center = Point3D(0,0,0)
    i = False
    for vtx in vertexList:
        center += vtx.center
        i+=1
    if i:
        center /= i
    return center

def flatten(thing):
    """ get nested tuple structure like quadrents and flatten it """
    if type(thing) == tuple:
        for element in thing:
            for thing in flatten(element):
                yield thing
    else:
        yield thing

def splitIntoQuadrants(vertexList,center):
    """
        +---+---+    +---+---+
        | 1 | 2 |    | 5 | 6 |
        +---+---+    +---+---+
        | 3 | 4 |    | 7 | 8 |
        +---+---+    +---+---+
        put all poly wraps into quadrents
    """
    quadrants = ((([],[]),
                 ([],[])),
                 (([],[]),
                  ([],[])))
    for vtx in vertexList:
        vtxPos = vtx.center
        x =  vtxPos[0] > center[0]
        y =  vtxPos[1] > center[1]
        z =  vtxPos[2] > center[2]
        quadrants[x][y][z].append(vtx)
    quadrants = flatten(quadrants)
    return quadrants

class Polywrap:
    """
        its a class that defines polygons center
        so that it does not have to be recomputed
    """
    polygon = None
    center = None
   
    def __str__(self):
        """ some visualization to aid debugging """
        return str(self.polygon.getNumVertices())+":"+str(self.center)
   
def genPolyWraps(group):
    """ generate a list of polywraps form a group of polygons """
    for polygon in iterChildren(group):
        if type(polygon) == EggPolygon:
            center = Vec3D()
            i = False
            for vtx in iterVertexes(polygon):
                center += vtx.getPos3()
                i += 1
            if i : center /= i
            pw = Polywrap()
            pw.polygon = polygon
            pw.center = center
            yield pw
         
def buildOctree(group):
    """ build an octree form a egg group """
    global verbose
    group.triangulatePolygons(0xff)
    polywraps = [i for i in genPolyWraps(group)]
    if verbose: print len(polywraps),"triangles"
    center = getCenter(polywraps)
    quadrants = splitIntoQuadrants(polywraps,center)
    eg = EggGroup('octree-root')
    for node in recr(quadrants):
        eg.addChild(node)
    return eg

def recr(quadrants,indent=0):
    """
        visit each quadrent and create octree there
        all the end consolidate all octrees into egg groups
    """
    global verbose,maxNumber
    qs = [i for i in quadrants]
    if verbose: print "    "*indent,"8 quadrents have ",[len(i) for i in qs]," triangles"
    for quadrent in qs:
        if len(quadrent) == 0:
            if verbose: print "    "*indent," no triangles at this quadrent"
            continue
        elif len(quadrent) <= maxNumber:
            center = getCenter(quadrent)
            if verbose: print "    "*indent," triangle center", center, len(quadrent)
            eg = EggGroup('leaf %i tri'%len(quadrent))
            eg.addObjectType('barrier')
            for pw in quadrent:
                eg.addChild(pw.polygon)
                if eg.getFirstChild : yield eg
        else:
            eg = EggGroup('branch-%i'%indent)
            center = getCenter(quadrent)
            for node in recr(splitIntoQuadrants(quadrent,center),indent+1):
                eg.addChild(node)
            if eg.getFirstChild : yield eg
     
def iterChildren(eggNode):
    """ iterate all children of a node """
    try:
        child = eggNode.getFirstChild()
        while child:
            yield child
            child = eggNode.getNextChild()
    except:
        pass
   
def iterVertexes(eggNode):
    """ iterate all vertexes of polygon or polylist """
    try:
        index = eggNode.getHighestIndex()
        for i in xrange(index+1):
            yield eggNode.getVertex(i)
    except:
        index = eggNode.getNumVertices()
        for i in xrange(index):
            yield eggNode.getVertex(i)
        pass

def eggLs(eggNode,indent=0):
    """ list whats in our egg """
    if eggNode.__class__.__name__ != "EggPolygon":
        print " "*indent+eggNode.__class__.__name__+" "+eggNode.getName()
        for eggChildren in iterChildren(eggNode):
            eggLs(eggChildren,indent+1)
       
def eggStripTexture(eggNode):
    """ strip textures and materials """
    if eggNode.__class__ == EggPolygon:
        eggNode.clearTexture()
        eggNode.clearMaterial()       
    else:
        for eggChildren in iterChildren(eggNode):
            eggStripTexture(eggChildren)
           
           
def octreefy(infile,outfile):
    """
        octreefy infile and write to outfile
        using the buildOctree functions
    """
    egg = EggData()
    egg.read(Filename(infile))
    eggStripTexture(egg)
    group = egg
    vertexPool = False
    # find the fist group and fine the first vertexPool
    # you might have to mess with this if your egg files
    # are in odd format
    for child in iterChildren(egg):
        if type(child) == EggVertexPool:
            vertexPool = child
        if type(child) == EggGroup:
            group = child
    # if we have not found the vertexPool it must be inside
    if not vertexPool:
        for child in iterChildren(group):
            if type(child) == EggVertexPool:
                vertexPool = child
    if vertexPool and group:
        ed = EggData()
        ed.setCoordinateSystem(egg.getCoordinateSystem())
        ed.addChild(vertexPool)
        ed.addChild(buildOctree(group))
        if listResultingEgg: eggLs(ed)
        ed.writeEgg(Filename(outfile))
       
def main():
    """ interface to our egg octreefier """
    try:
        optlist, list = getopt.getopt(sys.argv[1:], 'hlvo:n:')
    except Exception,e:
        print e
        sys.exit(0)
    global verbose,listResultingEgg,maxNumber
    outfile = False
    for opt in optlist:
        if opt[0] == '-h':
            print __doc__
            sys.exit(0)
        if opt[0] == '-l':
            listResultingEgg = True
        if opt[0] == '-v':
            verbose = True
        if opt[0] == '-n':
            maxNumber = int(opt[1])
        if opt[0] == '-o':
            outfile = opt[1]
    if outfile and len(list) > 1:
        print "error can have an outfile and more then one infile"
        sys.exit(0)
       
    for file in list:
        if '.egg' in file:
            if verbose: print "processing",file
            if outfile:
                octreefy(file,outfile)
            else:
                octreefy(file,file.replace(".egg","-octree.egg"))
                 
if __name__ == "__main__":
    import os
    main() 
