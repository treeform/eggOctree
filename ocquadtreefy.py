"""
                                       _                            ___
                                      | | _                        / __) _
  ___    ____  ____  _   _   ____   _ | || |_    ____  ____  ____ | |__ | |_  _   _
 / _ \  / ___)/ _  || | | | / _  | / || ||  _)  / ___)/ _  )/ _  )|  __)|  _)| | | |
| |_| |( (___| | | || |_| |( ( | |( (_| || |__ | |   ( (/ /( (/ / | |   | |__| |_| |
 \___/  \____)\_|| | \____| \_||_| \____| \___)|_|    \____)\____)|_|    \___)\__  |
                 |_| original by treeform, modified by mindstormss           (____/
                     bug fixes and quadtree support by fenrirwolf


This is a replacement of raytaller's wonderful Egg Octree script.

Many people had problem using it (I always guessed wrong about the size of
cells) and it generated many "empty" branches which this one does not.  This one
also uses geoms/primitives instead of egg data for real time usage

original see : ( http://panda3d.org/phpbb2/viewtopic.php?t=2502 )
treeform's rewrite: ( http://www.panda3d.org/phpbb2/viewtopic.php?p=23267#23267 )
mindstormss's mod: ( http://www.panda3d.org/phpbb2/viewtopic.php?p=41362#41362 )
fenrirwolf's mod: ( http://www.panda3d.org/phpbb2/viewtopic.php?p=44007#44007 )

This script like the original also released under the WTFPL license.

Fenrir: I have also modified the script to support quad trees, plus fixed a bug
with calculating polywrap centers.  I removed combine(), because I felt it was
redundant.

Usage:
    newnode = octreefy (node, type='colpoly', maxDensity=64, verbose=0)
    newnode = quadtreefy (...)   [same parameters as above]

The input node is the node to be turned into an octree.  This can either be a
GeomNode or a PandaNode with a GeomNode child.  Will create a quad/octree for
this node.  Note that we do not expect multiple GeomNodes -- Flatten your
heirarchy first before you hand it over.  (If you want the old combiner method
back, just copy the combine function over from Mindstormss's script.)

The quad/octree is returned as a new node.  This node does not contain the
original node's states, so you will need to assign as appropriate.

Set verbose to 1 if you want to see a breakdown of what is returned.  Set it to
2 if you would also like to see tight bounds plus a random color for each leaf.

The type parameter controls what kind of geometry is returned.  If it set to
'geom', then a GeomNode with Primitives will be returned.  If it set to
'colpoly', then CollisionPolygons are returned.  You want to use CollisionPolys
if you intend to use this quad/octree for collisions, as it is much faster than
using GeomNodes.
"""

def getCenter(vertexList):
    """ Get a list of Polywraps and figure out their center """
    # Loop on the vertices determine the bounding box
    center = Point3(0)
    i = 0
    for vtx in vertexList:
        center += vtx.center
        i+=1
    if i:
        center /= i
    return center

def flatten(thing):
    """ Get nested tuple structure like quadrents and flatten it """
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
      Put all poly wraps into quadrants
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

def splitInto2DQuads(vertexList, center):
    """
        +---+---+
        | 1 | 2 |
        +---+---+
        | 3 | 4 |
        +---+---+
        Put all polywraps into 2d quads.
        Note we assume Z-up for standard Panda coordinate space
    """
    quadrants = (([],[]),
                 ([],[]))
    for vtx in vertexList:
        vtxPos = vtx.center
        x =  vtxPos[0] > center[0]
        y =  vtxPos[1] > center[1]
        quadrants[x][y].append(vtx)
    quadrants = flatten(quadrants)
    return quadrants

class Polywrap:
    """
        It's a class that defines polygons center, so that it does not have to
        be recomputed.
    """
    polygon = None
    center = None

    def __str__(self):
        """ Some visualization to aid debugging """
        return str(self.polygon.getNumVertices())+":"+str(self.center)

def genPolyWraps(vdata, prim):
    """ Generate a list of polywraps from a group of polygons """
    vertex = GeomVertexReader(vdata, 'vertex')
    for p in range(prim.getNumPrimitives()):
        s = prim.getPrimitiveStart(p)
        e = prim.getPrimitiveEnd(p)
        center = Vec3(0)
        num = 0
        for i in range(s, e):
            vertex.setRow(prim.getVertex(i))
            center+=vertex.getData3f()
        center/=e-s
        pw = Polywrap()
        pw.polygon = p
        pw.center = center
        yield pw

def recr(quadrants, vdata, prim, type, maxDensity, verbose, quadsplitter, \
        indent=0):
    """
    Visit each quadrant and create a tree.

    quadrants = iterator of quadrants that have been generated for this
        branch

    vdata,prim = data carried over from initial combine

    type = 'geom' or 'colpoly', indicates what kind of PandaNodes to
        generate

    maxDensity = How many triangles to allow per leaf

    verbose = Verbosity debug level, 0=lowest, 2=highest

    quadsplitter = The quadrant space splitting function (can be quadtree or
        octree)
    """
    vertex = GeomVertexReader(vdata,'vertex')
    qs = [i for i in quadrants]
    if verbose: print "    "*indent,len(qs),"quadrants have ",[len(i) for i in qs]," triangles"
    for quadrant in qs:
        if len(quadrant) == 0:
            if verbose: print "    "*indent," no triangles at this quadrant"
            continue
        elif len(quadrant) <= maxDensity:
            center = getCenter(quadrant)
            if verbose: print "    "*indent," triangle center", center, len(quadrant)
            p = GeomTriangles(Geom.UHStatic)
            if type is 'colpoly':
                colNode = CollisionNode('leaf-%i'%indent)
            for pw in quadrant:
                s = prim.getPrimitiveStart(pw.polygon)
                e = prim.getPrimitiveEnd(pw.polygon)
                l = []
                for i in range(s,e):
                    l.append(prim.getVertex(i))
                if type is 'geom':
                    p.addVertices(*l)
                    p.closePrimitive()
                elif type is 'colpoly':
                    for i in range(0,len(l),3):
                        v = []
                        for i2 in range(3):
                            vertex.setRow(l[i+i2])
                            v.append(vertex.getData3f())
                        p = CollisionPolygon(*v)
                        colNode.addSolid(p)

            node = NodePath('leaf-%i'%indent)
            if type is 'geom':
                geom = Geom(vdata)
                geom.clearPrimitives()
                geom.addPrimitive(p)
                geomNode = GeomNode('gnode')
                geomNode.addGeom(geom)
                node.attachNewNode(geomNode)
            elif type is 'colpoly':
                node.attachNewNode(colNode)
            if verbose>1:
                if type is 'geom':
                    node.setColor (random.uniform(0,1), random.uniform(0,1), \
                        random.uniform(0,1), 1)
                node.showTightBounds()
            yield node
        else:
            node = NodePath('branch-%i'%indent)
            center = getCenter(quadrant)
            for n in recr(quadsplitter(quadrant,center), vdata, prim, type, \
                                maxDensity, verbose, quadsplitter, indent+1):
                n.reparentTo(node)
            if verbose>1:
                if type is 'geom':
                    node.setColor (random.uniform(0,1), random.uniform(0,1), \
                        random.uniform(0,1), 1)
                node.showTightBounds()
            yield node

def octreefy(node, type='geom', maxDensity=4, verbose=0, \
    normal=False, texcoord=False, binormal=False):
    """
    Octreefy this node and it's children.

    type = 'geom' or 'colpoly'.  Will generate either GeomNodes or
        CollisionPolys.

    maxDensity = How 'deep' to make the tree, will make sure each leaf has
        no more than X triangles in it

    verbose = Enable some debugging info, set to 1 for console output, 2
        for debug info
    """
    # Sanity check
    if type is not 'geom' and type is not 'colpoly':
        print 'Unknown type of',type,',only geom or colpoly allowed!'
        return

    # Let's look for a GeomNode under this nodepath.
    # We don't search too deep, only checking the first child, because we are
    # expecting a flattened structure.
    if not node.node().isGeomNode():
        geomNode = node.getChild(0).node() # Try to get first child
    else:
        geomNode = node.node()
    if not geomNode.isGeomNode():
        print 'We require a single GeomNode.  Flatten first!'
        return
    geom = geomNode.getGeom(0).decompose()
    vdata = geom.getVertexData()
    prim = geom.getPrimitive(0)

    # Generate polywraps for our vertices
    polywraps = [i for i in genPolyWraps(vdata,prim)]
    if verbose: print len(polywraps),"triangles in polywraps"

    # Find the center of the entire mess
    center = getCenter(polywraps)

    # Do first split
    quadrants = splitIntoQuadrants(polywraps, center)

    # Now let's start working our way down the tree
    node = NodePath(PandaNode('octree-root'))
    for n in recr(quadrants, vdata, prim, type, maxDensity, verbose, splitIntoQuadrants):
        n.reparentTo(node)

    return node


def quadtreefy(node, type='geom', maxDensity=4, verbose=0, \
    normal=False, texcoord=False, binormal=False):
    """
    quadtreefy this node and it's children.

    type = 'geom' or 'colpoly'.  Will generate either GeomNodes or
        CollisionPolys.

    maxDensity = How 'deep' to make the tree, will make sure each leaf has
        no more than X triangles in it

    verbose = Enable some debugging info, set to 1 for console output, 2
        for debug info
    """
    # Sanity check
    if type is not 'geom' and type is not 'colpoly':
        print 'Unknown type of',type,',only geom or colpoly allowed!'
        return

    # Let's look for a GeomNode under this nodepath.
    # We don't search too deep, only checking the first child, because we are
    # expecting a flattened structure.
    if not node.node().isGeomNode():
        geomNode = node.getChild(0).node() # Try to get first child
    else:
        geomNode = node.node()
    if not geomNode.isGeomNode():
        print 'We require a single GeomNode.  Flatten first!'
        return
    geom = geomNode.getGeom(0).decompose()
    vdata = geom.getVertexData()
    prim = geom.getPrimitive(0)

    # Generate polywraps for our vertices
    polywraps = [i for i in genPolyWraps(vdata, prim)]
    if verbose: print len(polywraps), 'triangles in polywraps'

    # Find the center of the entire mess
    center = getCenter(polywraps)
    if verbose: print center, 'is center'

    # Do first split
    quadrants = splitInto2DQuads(polywraps, center)

    # Now let's start working our way down the tree
    node = NodePath(PandaNode('quadtree-root'))
    for n in recr(quadrants, vdata, prim, type, maxDensity, verbose, splitInto2DQuads):
        n.reparentTo(node)

    return node

