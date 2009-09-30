
"""
                             _                 
                            | |               
  ___  __ _  __ _  ___   ___| |_ _ __ ___  ___
 / _ \/ _` |/ _` |/ _ \ / __| __| '__/ _ \/ _ \
|  __/ (_| | (_| | (_) | (__| |_| | |  __/  __/
 \___|\__, |\__, |\___/ \___|\__|_|  \___|\___|
       __/ | __/ | by treeform                           
      |___/ |___/  modified by mindstormss      
            
     This is a replacement of raytaller wonderful
     Egg Octree script many people had problem using it
     ( i always guessed wrong about the size of cells )
     and it generated many "empty" branches which this
     one does not.  This one also uses geoms/primitives 
     instead of egg data for real time usage
     original see : ( http://panda3d.org/phpbb2/viewtopic.php?t=2502 )
     This script like the original also released under the WTFPL license.
     Usage: octreefy(node)
     node -> node to be turned into an octree. Will create 
     an octree for this node and a seperate octree for each 
     child of this node returns the octree as a node. only vertex     
     information is transfered to this new node
"""
__all__ = ['octreefy']
from pandac.PandaModules import *
    
def getCenter(vertexList):
    """ get a list of Polywraps and figure out their center """
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
    """ get nested tuple structure like quadrents and flatten it """
    if type(thing) == tuple:
        for element in thing:
            for thing in flatten(element):
                yield thing
    else:
        yield thing

def splitIntoQuadrants(vertexList,center):
    """
        +---+---+     +---+---+
        | 1 | 2 |     | 5 | 6 |
        +---+---+     +---+---+
        | 3 | 4 |     | 7 | 8 |
        +---+---+     +---+---+
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
    
def genPolyWraps(vdata,prim):
    """ generate a list of polywraps from a group of polygons """
    vertex = GeomVertexReader(vdata, 'vertex')
    for p in range(prim.getNumPrimitives()):
        s = prim.getPrimitiveStart(p)
        e = prim.getPrimitiveEnd(p)
        center = Vec3(0)
        num = 0
        for i in range(s, e):
            vertex.setRow(prim.getVertex(i))
            center+=vertex.getData3f()
            i+=1
        if i: center/=i
        pw = Polywrap()
        pw.polygon = p
        pw.center = center
        yield pw
        
def buildOctree(vdata,prim,maxNumber,verbose):
    """ build an octree from a primitive and vertex data """
    polywraps = [i for i in genPolyWraps(vdata,prim)]
    if verbose: print len(polywraps),"triangles"
    center = getCenter(polywraps)
    quadrants = splitIntoQuadrants(polywraps,center)
    node = NodePath(PandaNode('octree-root'))
    for n in recr(quadrants,vdata,prim,maxNumber,verbose):
        n.reparentTo(node)
    return node

def recr2(quadrants,vdata,prim,maxNumber,verbose,indent=0):
    """
        visit each quadrent and create octree there
    """
    vertex = GeomVertexReader(vdata,'vertex')
    qs = [i for i in quadrants]
    if verbose: print "     "*indent,"8 quadrents have ",[len(i) for i in qs]," triangles"
    for quadrent in qs:
        if len(quadrent) == 0:
            if verbose: print "     "*indent," no triangles at this quadrent"
            continue
        elif len(quadrent) <= maxNumber:
            center = getCenter(quadrent)
            if verbose: print "     "*indent," triangle center", center, len(quadrent)
            p = GeomTriangles(Geom.UHStatic)
            for pw in quadrent:
                s = prim.getPrimitiveStart(pw.polygon)
                e = prim.getPrimitiveEnd(pw.polygon)
                l = []
                for i in range(s,e):
                    l.append(prim.getVertex(i))
                p.addVertices(*l)
                p.closePrimitive()
            geom = Geom(vdata)
            geom.clearPrimitives()
            geom.addPrimitive(p)
            geomnode = GeomNode('gnode')
            geomnode.addGeom(geom)
            node = NodePath('leaf-%i'%indent)
            node.attachNewNode(geomnode)
            yield node
        else:
            node = NodePath('branch-%i'%indent)
            center = getCenter(quadrent)
            for n in recr(splitIntoQuadrants(quadrent,center),vdata,prim,maxNumber,verbose,indent+1):
                n.reparentTo(node)
            yield node

def recr(quadrants,vdata,prim,maxNumber,verbose,indent=0):
    """
        visit each quadrent and create octree there
    """
    vertex = GeomVertexReader(vdata,'vertex')
    qs = [i for i in quadrants]
    if verbose: print "     "*indent,"8 quadrents have ",[len(i) for i in qs]," triangles"
    for quadrent in qs:
        if len(quadrent) == 0:
            if verbose: print "     "*indent," no triangles at this quadrent"
            continue
        elif len(quadrent) <= maxNumber:
            center = getCenter(quadrent)
            if verbose: print "     "*indent," triangle center", center, len(quadrent)
            p = GeomTriangles(Geom.UHStatic)
            collNode = CollisionNode('leaf-%i'%indent)
            
            for pw in quadrent:
                s = prim.getPrimitiveStart(pw.polygon)
                e = prim.getPrimitiveEnd(pw.polygon)
                l = []
                for i in range(s,e):
                    l.append(prim.getVertex(i))
                for i in range(0,len(l),3):
                    v = []
                    for i2 in range(3):
                        vertex.setRow(l[i+i2])
                        v.append(Point3(vertex.getData3f()))
                    if not CollisionPolygon.verifyPoints(*v): continue    #not a valid triangle
                    p = CollisionPolygon(*v)
                    collNode.addSolid(p)
            
            node = NodePath('leaf-%i'%indent)
            node.attachNewNode(collNode)
            yield node
        else:
            node = NodePath('branch-%i'%indent)
            center = getCenter(quadrent)
            for n in recr(splitIntoQuadrants(quadrent,center),vdata,prim,maxNumber,verbose,indent+1):
                n.reparentTo(node)
            yield node
    
def combine(node):
    """
          combines all of the geoms into one. a preprocessing step
    """
    newVdata = GeomVertexData('name', GeomVertexFormat.getV3(), Geom.UHStatic)
    vertexWriter = GeomVertexWriter(newVdata, 'vertex')
    newPrim = GeomTriangles(Geom.UHStatic)
    startingPos = 0
    pos = 0
    
    for node in node.findAllMatches('**/+GeomNode'):
        geomNode = node.node()
        for i in range(geomNode.getNumGeoms()):
            geom = geomNode.getGeom(i).decompose()
            vdata = geom.getVertexData()
            vertexReader = GeomVertexReader(vdata,'vertex')
            while not vertexReader.isAtEnd():
                v = vertexReader.getData3f()
                vertexWriter.addData3f(v[0],v[1],v[2])
                pos+=1
            for i in range(geom.getNumPrimitives()):
                prim = geom.getPrimitive(i)
                for i2 in range(prim.getNumPrimitives()):
                    s = prim.getPrimitiveStart(i2)
                    e = prim.getPrimitiveEnd(i2)
                    for i in range(s, e):
                        newPrim.addVertex(prim.getVertex(i)+startingPos)
                    newPrim.closePrimitive()
            startingPos=pos
    return [newVdata,newPrim]
            
def octreefy(node,maxNumber=3,verbose=False):
    """
        octreefy this node and it's children
        using the buildOctree functions
    """
    vdata,prim = combine(node)    #combine all of the geoms into one vertex/triangle list
    #print vdata
    #print prim
    return buildOctree(vdata,prim,maxNumber,verbose)    #build the octree 
