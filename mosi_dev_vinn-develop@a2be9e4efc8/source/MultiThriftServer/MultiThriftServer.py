
from .gen_code.ttypes import TPosture, TBone, TVector3, TGait, TQuaternion
from .gen_code import T_multi_directional_motion_server
from ...controlers.directional_controller import DirectionalController

from thrift import Thrift
from thrift.transport import TSocket, TTransport
from thrift.protocol import TBinaryProtocol
from thrift.server import TServer

from ...utils import global_to_local_pos

import threading
import numpy as np
import copy

import time
DEBUG_TIMING = False

# def read_BVH(file):
# 	lines = []
# 	with open(file) as f:
# 		line = f.readline()
# 		while ("MOTION" not in line):
# 			if not line.strip() == "":
# 				lines.append(line.strip())
# 			line = f.readline()
# 		bonelinst = []
# 		bid = 0
# 		mapping = {}
# 		current_bone_name = ""
# 		current_offset = np.array([0.0,0.0,0.0])
# 		last_bone_name = ""
# 		i = 0
# 		while(i < len(lines)):
# 			# if "HIERARCHY" in lines[i] or "CHANNELS" in lines[i] or "{" in lines[i]:
# 			# 	continue
# 			if "End Site" in lines[i]:
# 				i+= 4
# 				continue
# 			elif "}" in lines[i]:
# 				last_bone_name = bonelinst[mapping[last_bone_name]].parent

# 			elif "JOINT" in lines[i] or "ROOT" in lines[i]:
# 				params = lines[i].split()
# 				current_bone_name = params[1].strip()

# 			elif "OFFSET" in lines[i]:
# 				if current_bone_name != "":
# 					params = lines[i].split()
# 					parent_offset = np.array([0,0,0])
# 					if last_bone_name != "":
# 						parent_offset = TVector3_2np(bonelinst[mapping[last_bone_name]].Position)
# 					offset = np.array([float(params[1]), -float(params[2]), float(params[3])]) * 5.333
# 					current_offset = np_2TVector3(parent_offset + offset)#TVector3(float(params[1]), float(params[2]), float(params[3]))
# 					tb = TBone(current_bone_name, current_offset, children=[], parent=last_bone_name)
# 					bonelinst.append(tb)
# 					mapping[current_bone_name] = bid
# 					bid += 1
# 					last_bone_name = current_bone_name
# 					current_bone_name = ""
# 			i += 1
		
# 		for tb in bonelinst:
# 			if tb.parent != "":
# 				pid = mapping[tb.parent]
# 				bonelinst[pid].children.append(tb.name)
# 	return TPosture(bonelinst, mapping, TVector3(0,0,0), 0.0)
	
def TVector3_2np(x):
	return np.array([x.x, x.y, x.z])
def np_2TVector3(x):
	return TVector3(x[0], x[1], x[2])

class MotionServer:
	def __init__(self, controller: DirectionalController):
		self.log = {}
		self.base_controller = controller
		self.zero_posture = self.build_zero_posture("local_position")#read_BVH(bvh_path)
		self.zero_posutre2 = self.build_zero_posture()
		self.session_controllers = {}
		self.session_counter = 0

	def registerSession(self):
		self.session_counter += 1
		self.session_controllers[self.session_counter] = self.base_controller.copy()
		return self.session_counter
	
	def build_zero_posture(self, position_str = "position"):
		zp = self.base_controller.zero_posture
		bonelist = []
		mapping = {}
		for bone in zp:
			mapping[bone["name"]] = (bone["index"])
		for bone in zp:
			children = [c for c in bone["children"]]

			position = np.array([float(bone[position_str][0]), float(bone[position_str][1]), float(bone[position_str][2])])
			if "local" in position_str:
				position = position / 100
			else:
				position = position
			position = np_2TVector3(position)
			
			rotation = TQuaternion(float(bone["local_rotation"][0]), float(bone["local_rotation"][1]), float(bone["local_rotation"][2]), float(bone["local_rotation"][3]))
			tb = TBone(bone["name"], position, rotation, children, bone["parent"])
			bonelist.append(tb)
		return TPosture(bonelist, mapping, TVector3(0,0,0), 0.0)

	def getZeroPosture(self):
		return self.zero_posture

	def fetchFrame(self, dtime : float, currentPosture : TPosture, direction : TVector3, gait : TGait, session_counter : int):
		#newphase = self.controller.lastphase + self.controller.output.getdDPhase()
		if DEBUG_TIMING:
			start_time = time.time()
		if session_counter not in self.session_controllers.keys():
			self.session_controllers[session_counter] = self.base_controller.copy()
			print("This is not right. Do propper session management here. had to create a session for %f on the fly. "%session_counter)
		self.session_controllers[session_counter].pre_render(TVector3_2np(direction), self.session_controllers[session_counter].lastphase)
		posture = self.__char2TPosture(session_counter)
		#posture = self.zero_posutre2
		self.session_controllers[session_counter].post_render()
		if DEBUG_TIMING:
			totime = time.time() - start_time
			print("fetch frame: %f equals hypothetical %f fps"%(totime, 1/totime))
		return posture
	
	def __char2TPosture(self):
		posture = copy.deepcopy(self.zero_posutre2)
		pose = self.controller.getPose()
		for i in range(len(pose)):
			#pos = global_to_local_pos(char.joint_positions[i], char.root_position, char.root_rotation)
			posture.bones[i].position = np_2TVector3(pose[i])
		
		root_pos, root_rot = self.controller.getWorldPosRot()
		
		posture.location = np_2TVector3(root_pos)
		posture.rotation = root_rot
		return posture


def CREATE_MOTION_SERVER(controller):
	handler = MotionServer(controller)
	processor = T_multi_directional_motion_server.Processor(handler)
	transport = TSocket.TServerSocket(host="127.0.0.1", port=9999)
	tfactory = TTransport.TBufferedTransportFactory()
	pfactory = TBinaryProtocol.TBinaryProtocolFactory()

	#server = TServer.TSimpleServer(processor, transport, tfactory, pfactory)
	server = TServer.TThreadPoolServer(processor, transport, tfactory, pfactory)


	
	thread = threading.Thread(target=server.serve)
	thread.daemon = True
	thread.start()
	thread.join()

	

	# server.serve()
	# server.stop()