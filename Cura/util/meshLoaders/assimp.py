"""
Assimp file mesh loader.
"""
import numpy
from Cura.util import printableObject

supported = False

try:
	print "importing pyassimp"
	from pyassimp import pyassimp
	postprocessing = (0x8000 | 0x8)
	print "importing dll"
	pyassimp._assimp_lib.get_extension_list = pyassimp._assimp_lib.dll.aiGetExtensionList
	print "supported!"
	supported = True
except:
	try:
		print "importing pyassimp"
		import pyassimp
		print "importing postprocess"
		from pyassimp import postprocess
		postprocessing = (postprocess.aiProcess_SortByPType | postprocess.aiProcess_Triangulate)
		print "importing dll"
		pyassimp._assimp_lib.get_extension_list = pyassimp._assimp_lib.dll.aiGetExtensionList
		print "supported!"
		supported = True
	except:
		supported = False

#supported = False

print "assimp is : %ssupported" % ("" if supported else "NOT ")

def get_extension_list():
	if supported:
		from ctypes import byref
		from pyassimp import structs
		extensionList = structs.String()
		pyassimp._assimp_lib.get_extension_list(byref(extensionList))
		return extensionList.data
	else:
		return ""

def loadSupportedExtensions():
	ext = map(lambda x: x[1:], get_extension_list().split(';'))
	print "Supported extensions : %s" % str(ext)
	return ext

class PropertyGetter(dict):
    def __getitem__(self, key):
        semantic = 0
        if isinstance(key, tuple):
            key, semantic = key

        return dict.__getitem__(self, (key, semantic))

    def keys(self):
        for k in dict.keys(self):
            yield k[0]

    def __iter__(self):
        return self.keys()

    def items(self):
        for k, v in dict.items(self):
            yield k[0], v


def _get_properties(properties, length): 
    """
    Convenience Function to get the material properties as a dict
    and values in a python format.
    """
    from pyassimp import structs
    result = {}
    #read all properties
    for p in [properties[i] for i in range(length)]:
        #the name
        p = p.contents
        key = (str(p.mKey.data.decode("utf-8")).split('.')[1], p.mSemantic)

        #the data
        from ctypes import POINTER, cast, c_int, c_float, sizeof
        if p.mType == 1:
            arr = cast(p.mData, POINTER(c_float * int(p.mDataLength/sizeof(c_float)) )).contents
            value = [x for x in arr]
        elif p.mType == 3: #string can't be an array
            value = cast(p.mData, POINTER(structs.String)).contents.data.decode("utf-8")
        elif p.mType == 4:
            arr = cast(p.mData, POINTER(c_int * int(p.mDataLength/sizeof(c_int)) )).contents
            value = [x for x in arr]
        else:
            value = p.mData[:p.mDataLength]

        if len(value) == 1:
            [value] = value

        result[key] = value

    return PropertyGetter(result)

def recur_node(node,level = 0):
	if hasattr(node, 'contents'):
		name = node.contents.mName.data
		children = node.contents.mChildren[0:node.contents.mNumChildren]
		meshes = node.contents.mMeshes[0:node.contents.mNumMeshes]
	else:
		name = str(node)
		children = node.children
		meshes = node.contents.mMeshes[0:node.contents.mNumMeshes]
	print("  " + "\t" * level + name + " (%d meshes = %s)" % (node.contents.mNumMeshes, str(meshes)))
	for child in children:
		recur_node(child, level + 1)

def print_scene_info(filename, scene):
	print("MODEL:" + filename)
	print

	#write some statistics
	print("SCENE:")
	print("	 meshes:" + str(len(scene.meshes)))
	print("	 materials:" + str(len(scene.materials)))
	print("	 textures:" + str(len(scene.textures)))
	print

	print("NODES:")
	recur_node(scene.mRootNode)

	print("MESHES:")
	for index, mesh in enumerate(scene.meshes):
		print("	 MESH" + str(index+1) + " " + str(mesh.mName.data))
		print("	   material id:" + str(mesh.mMaterialIndex+1))
		print("	   vertices:" + str(len(mesh.vertices)))
		print("	   first 3 verts:\n" + str(mesh.vertices[:3]))
		if mesh.normals.count > 0:
				print("	   first 3 normals:\n" + str(mesh.normals[:3]))
		else:
				print("	   no normals")
		print("	   colors:" + str(len(mesh.colors)))
		tcs = mesh.texcoords
		if tcs.count > 0:
			for index, tc in enumerate(tcs):
				print("	   texture-coords "+ str(index) + ":" + str(len(tcs[index])) + " first3:" + str(tcs[index][:3]))

		else:
			print("	   no texture coordinates")
		#print("	   uv-component-count:" + str(len(mesh.numuvcomponents)))
		print("	   faces:" + str(len(mesh.faces)) + " -> type : " + str(mesh.mPrimitiveTypes))
		print("	   bones:" + str(len(mesh.bones)) + " -> first:" + str([str(b) for b in mesh.bones[:3]]))
		print

	print("MATERIALS:")
	for index, material in enumerate(scene.materials):
		print("	 MATERIAL (id:" + str(index+1) + ")")
		properties = _get_properties(material.mProperties, material.mNumProperties)
		for key, value in properties.items():
			print("	   %s: %s" % (key, value))
	print

	print("TEXTURES:")
	for index, texture in enumerate(scene.textures):
		print("	 TEXTURE" + str(index+1))
		print("	   width:" + str(texture.width))
		print("	   height:" + str(texture.height))
		print("	   hint:" + str(texture.achformathint))
		print("	   data (size):" + str(len(texture.data)))

def countMeshFacesNodeRecursive(count, scene, node):
	children = node.contents.mChildren[0:node.contents.mNumChildren]
	meshes = node.contents.mMeshes[0:node.contents.mNumMeshes]
	if len(meshes) > 0:
		for mesh_id in meshes:
			mesh = scene.meshes[mesh_id]
			if mesh.mPrimitiveTypes == 4: # Triangles
				count += mesh.mNumFaces

	for child in children:
		count = countMeshFacesNodeRecursive(count, scene, child)

	return count

def loadMeshNodeRecursive(m, scene, node):
	name = str(node.contents.mName.data)
	children = node.contents.mChildren[0:node.contents.mNumChildren]
	meshes = node.contents.mMeshes[0:node.contents.mNumMeshes]
	transformation = node.contents.mTransformation

	print "Loading meshes from node %s" % (name)
	if len(meshes) > 0:
		#obj = printableObject.printableObject(filename)
		#obj._name = str(name)
		for mesh_id in meshes:
			mesh = scene.meshes[mesh_id]
			if mesh.mPrimitiveTypes == 4: # Triangles
				#m = obj._addMesh()
				#m._prepareFaceCount(mesh.mNumFaces)
				print "Node has %d faces" % mesh.mNumFaces
				#vertices = numpy.matrix(mesh.vertices) * numpy.matrix(self._obj._matrix, numpy.float32)).getA()
				#return (numpy.matrix(self.vertexes, copy = False) * numpy.matrix(self._obj._matrix, numpy.float32)).getA()
				vertices = numpy.zeros((mesh.mNumFaces*3, 4), numpy.float32)
				for i in xrange(len(mesh.vertices)):
					vertices[i] = list(mesh.vertices[i]) + [1]
				#print mesh.vertices
				#print vertices
				transMatrix = [[transformation.a1, transformation.a2, transformation.a3, transformation.a4],
							   [transformation.b1, transformation.b2, transformation.b3, transformation.b4],
							   [transformation.c1, transformation.c2, transformation.c3, transformation.c4],
							   [transformation.d1, transformation.d2, transformation.d3, transformation.d4]]
				vertices = (numpy.matrix(vertices, copy = False) * numpy.matrix(transMatrix, numpy.float32)).getA()
				#print vertices
				#vertices = mesh.vertices
				for face in mesh.mFaces[0:mesh.mNumFaces]:
					v1 = vertices[face.mIndices[0]]
					v2 = vertices[face.mIndices[1]]
					v3 = vertices[face.mIndices[2]]
					m._addFace(v1[0], v1[1], v1[2], v2[0], v2[1], v2[2], v3[0], v3[1], v3[2])


	for child in children:
		loadMeshNodeRecursive(m, scene, child)

def loadMeshNodeRecursive2(filename, scene, node):
	name = str(node.contents.mName.data)
	children = node.contents.mChildren[0:node.contents.mNumChildren]
	meshes = node.contents.mMeshes[0:node.contents.mNumMeshes]

	print "Loading meshes from node %s" % (name)
	ret = []
	if len(meshes) > 0:
		obj = printableObject.printableObject(filename)
		obj._name = str(name)
		for mesh_id in meshes:
			mesh = scene.meshes[mesh_id]
			if mesh.mPrimitiveTypes == 4: # Triangles
				m = obj._addMesh()
				m._prepareFaceCount(mesh.mNumFaces)
				print "Mesh has %d faces" % mesh.mNumFaces
				vertices = mesh.vertices
				for face in mesh.mFaces[0:mesh.mNumFaces]:
					v1 = vertices[face.mIndices[0]]
					v2 = vertices[face.mIndices[1]]
					v3 = vertices[face.mIndices[2]]
					m._addFace(v1[0], v1[1], v1[2], v2[0], v2[1], v2[2], v3[0], v3[1], v3[2])
		obj._postProcessAfterLoad()
		ret.append(obj)


	for child in children:
		ret = ret + loadMeshNodeRecursive2(filename, scene, child)

	return ret

def loadMeshNodeRecursive3(filename, scene, node):
	name = str(node.contents.mName.data)
	children = node.contents.mChildren[0:node.contents.mNumChildren]
	meshes = node.contents.mMeshes[0:node.contents.mNumMeshes]

	print "Loading meshes 3 from node %s" % (name)
	ret = []
	if len(meshes) > 0:
		obj = printableObject.printableObject(filename)
		obj._name = str(name)
		numFaces = 0
		for mesh_id in meshes:
			mesh = scene.meshes[mesh_id]
			if mesh.mPrimitiveTypes == 4: # Triangles
				numFaces += mesh.mNumFaces
		m = obj._addMesh()
		m._prepareFaceCount(numFaces)
		print "Node has %d total faces" % numFaces
		for mesh_id in meshes:
			mesh = scene.meshes[mesh_id]
			if mesh.mPrimitiveTypes == 4: # Triangles
				print "Node has %d faces" % mesh.mNumFaces
				vertices = mesh.vertices
				for face in mesh.mFaces[0:mesh.mNumFaces]:
					v1 = vertices[face.mIndices[0]]
					v2 = vertices[face.mIndices[1]]
					v3 = vertices[face.mIndices[2]]
					m._addFace(v1[0], v1[1], v1[2], v2[0], v2[1], v2[2], v3[0], v3[1], v3[2])
		obj._postProcessAfterLoad()
		ret.append(obj)


	for child in children:
		ret = ret + loadMeshNodeRecursive3(filename, scene, child)

	return ret

def loadMeshes(filename):
	if supported is False:
		return []

	scene = pyassimp.load(filename, postprocessing)

	print_scene_info(filename, scene)

	if True:
		obj = printableObject.printableObject(filename)
		m = obj._addMesh()
		faces = countMeshFacesNodeRecursive(0, scene, scene.mRootNode)
		print "Total faces : %d" % faces
		m._prepareFaceCount(faces)
		loadMeshNodeRecursive(m, scene, scene.mRootNode)
		obj._postProcessAfterLoad()
		ret = [obj]
	elif False:
		ret = loadMeshNodeRecursive2(filename, scene, scene.mRootNode)
	else:
		ret = loadMeshNodeRecursive3(filename, scene, scene.mRootNode)

	# Finally release the model
	pyassimp.release(scene)
	return ret
