#!/usr/bin/env python
"""
BIONICLE: The Legend of Mata Nui Executable Patcher for build 2001-10-23
Version: 1.6.0

Copyright (c) 2018 JrMasterModelBuilder
Licensed under the Mozilla Public License, v. 2.0
"""

import os
import sys
import inspect
import argparse

def nop_pad(data, length):
	l = len(data)
	pad = length - l
	if pad < 0:
		raise Exception('Longer than padded length: %s > %s' % (l, length))
	return data + ([0x90] * pad)

class Patch():
	def __init__(self, fp):
		self.fp = fp

class PatchWin10(Patch):
	name = 'win10'
	description = 'Windows 10'
	def patch(self):
		# Check if pointer is -1, and if so always throw an exception.
		# In Windows 10 CloseHandle(-1) no longer returns -1 (undefined behavior).
		self.fp.seek(0xDB853) # 0x4DC453
		self.fp.write(bytearray([
			# Inserted before existing code.
			0x83, 0xBB, 0x24, 0x01, 0x00, 0x00, 0xFF, # cmp    DWORD PTR [ebx+0x124], 0xffffffff
			0x74, 0x04,                               # je     0xd
			# Existing code, shifted down, addresses corrected.
			0x85, 0xC0,                               # test   eax, eax
			0x75, 0x11,                               # jne    0x1e
			0x68, 0x18, 0x91, 0x83, 0x00,             # push   0x839118
			0x68, 0x40, 0x91, 0x83, 0x00,             # push   0x839140
			0xE8, 0x81, 0xCD, 0xFF, 0xFF,             # call   0xffffcd9d
			0x59,                                     # pop    ecx
			0x59,                                     # pop    ecx
			0xC6, 0x83, 0x20, 0x01, 0x00, 0x00, 0x00, # mov    BYTE PTR [ebx+0x120], 0x0
			0x8D, 0x65, 0xFC,                         # lea    esp, [ebp-0x4]
			0x5B,                                     # pop    ebx
			0x5D,                                     # pop    ebp
			0xC3                                      # ret
		]))

class PatchMatoranRGB(Patch):
	name = 'matoranrgb'
	description = 'Fix RGB values for Onu-Matoran'
	def patch(self):
		# Change RGB values from the Onu-Matoran for textures.
		self.fp.seek(0xB6F3) # 0x40C2F3
		self.fp.write(bytearray([
			0x6A, 0x27, # push   0x27
			0x6A, 0x27, # push   0x27
			0x6A, 0x27  # push   0x27
		]))

class PatchSoundTableAmount(Patch):
	name = 'soundtableamount'
	description = 'Avoid SoundTable error message'
	def patch(self):
		# Change expected amount of SoundTable entries to avoid error message.
		self.fp.seek(0x1CC4B4) # 0x5CD0B4
		self.fp.write(bytearray([
			0x81, 0xBD, 0xD4, 0xFE, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF
		]))

class PatchDebugPrint(Patch):
	name = 'debugprint'
	description = 'Append data to ReleaseInform.txt'
	def patch(self):
		# Change "w" to "r+b" to prevent ReleaseInform.txt from resetting every launch.
		self.fp.seek(0x6C9E7) # 0x46D5E7
		self.fp.write(bytearray([
			0x68, 0x38, 0x75, 0x74, 0x00 # push   offset aRB ; "r+b"
		]))

class PatchScreenRes4(Patch):
	name = 'screenres4'
	description = 'Set default screen resolution to 4'
	def patch(self):
		# Replace the default resolution int of 2 with the max of 4.
		self.fp.seek(0x347F2C) # 0x74A32C
		self.fp.write(bytearray([
			0x04
		]))

class PatchScreenResINI(Patch):
	name = 'screenresini'
	description = 'Allow ini to control screen resolution'
	def patch(self):
		# Replace GcGraphicsOptions::GetScreenResolution call in AppMain with constant 0.
		# This will force switch default case and prevent overwriting values from INI.
		self.fp.seek(0x13772D) # 0x53832D
		self.fp.write(bytearray([
			0xB8, 0x00, 0x00, 0x00, 0x00 # mov    eax, 0x0
		]))

		# Replace GcGraphicsOptions::GetScreenResolution switch statement in ScDrawableContext::Reset.
		# Instead call GcSaver::GetScreenData with the 7 required pointer arguments.
		# For the last 5 arguments, use a stack address that will be overwritten after this call.
		# For the first 2 arguments, pass the address of the height and width.
		# This code is somewhat unconventional and may look odd when run through a pseudocode generator.
		self.fp.seek(0x1585D0) # 0x5591D0
		self.fp.write(bytearray(nop_pad([
			0x8D, 0x85, 0x48, 0xFF, 0xFF, 0xFF, # lea     eax, [ebp-0xB8]
			0x50,                               # push    eax
			0x50,                               # push    eax
			0x50,                               # push    eax
			0x50,                               # push    eax
			0x50,                               # push    eax
			0x8D, 0x85, 0x44, 0xFF, 0xFF, 0xFF, # lea     eax, [ebp-0xBC]
			0x50,                               # push    eax
			0x8D, 0x85, 0x40, 0xFF, 0xFF, 0xFF, # lea     eax, [ebp-0xC0]
			0x50,                               # push    eax
			0xE8, 0x92, 0xBE, 0x07, 0x00,       # call    ?GetScreenData@GcSaver@@SAXAAG0AAE1111@Z
			0x83, 0xC4, 0x1C                    # add     esp, 0x1C
		], 0x6A)))

class PatchHVP(Patch):
	name = 'hvp'
	description = 'Hardward vertex processing'
	def patch(self):
		# By default the game attempts to draw with a negative near and far clip.
		# This does not work on any known graphics cards and is apparently very wrong.
		# This patch disables all the world inverting things that relate to this.
		# In Alpha 0.006 most of these changes were side effects to enabling SVP.
		# Essentially this patch corrects hardware vertex processing mode.

		# Disable negative near and far clip on the camera in GcViewPort::GcViewPort.
		# Replace GcGraphicsOptions::GetSVP call with constant 1.
		self.fp.seek(0x470E0) # 0x447CE0
		self.fp.write(bytearray([
			0xB0, 0x01, # mov    al, 0x1
			0x90,       # nop
			0x90,       # nop
			0x90        # nop
		]))

		# Disable inverted view matrix in GcLegoCamera::BuildViewMatrix.
		# Replace GcGraphicsOptions::GetSVP call with constant 1.
		self.fp.seek(0x5A2A2) # 0x45AEA2
		self.fp.write(bytearray([
			0xB0, 0x01, # mov    al, 0x1
			0x90,       # nop
			0x90,       # nop
			0x90        # nop
		]))

		# Disable inverted fog values in GcAreaDirector::SetFog.
		# Replace GcGraphicsOptions::GetSVP call with constant 1.
		self.fp.seek(0x89BA7) # 0x48A7A7
		self.fp.write(bytearray([
			0xB0, 0x01, # mov    al, 0x1
			0x90,       # nop
			0x90,       # nop
			0x90        # nop
		]))

		# Disable inverted projection matrix in ScPerspectiveCamera::BuildProjectionMatrix.
		# Replace GcGraphicsOptions::GetSVP call with constant 1.
		self.fp.seek(0x94866) # 0x495466
		self.fp.write(bytearray([
			0xB0, 0x01, # mov    al, 0x1
			0x90,       # nop
			0x90,       # nop
			0x90        # nop
		]))

		# Replace float sign inversion in GcGraphicsOptions::GetDrawDistance.
		# Prevents negative draw distance, resulting in an infinite far clip.
		self.fp.seek(0x1E46E6) # 0x5E52E6
		self.fp.write(bytearray([
			0x90, # nop
			0x90  # nop
		]))

		# Replace PI float with 0.0 in ScMatrix::RotateZ(PI) of GcSprite:Render.
		# Stop 2D sprites from being being flipped upside down.
		self.fp.seek(0x32D090) # 0x72F490
		self.fp.write(bytearray([
			0x00, 0x00, 0x00, 0x00 # float 0.0
		]))

class PatchDragonMelee(Patch):
	name = 'dragonmelee'
	description = 'Dragon melee attack fix'
	def patch(self):
		# Patch GcToa::CheckNearCharacters to have a special case for the dragon id 'drag'.
		# There is no Tahu-specific code in GcToa::UseSpecialAttack, it uses GcToa::StandardCloseAttack.
		# That uses GcToa::CheckNearCharacters, which only considers characters with 'aiin' controllers.
		# The dragon doesn't have one, and one cannot be added, so a special case is needed.
		# Fortunately there are precisely 10 bytes of redundant code in just the right place for it.
		self.fp.seek(0x16DE25) # 0x56EA25
		self.fp.write(bytearray([
			0x8B, 0x45, 0xD0,             # mov    eax, [ebp-0x30]
			0x3D, 0x67, 0x61, 0x72, 0x64, # cmp    eax, 0x64726167 ; 'drag'
			0x74, 0x26                    # je     0x28
		]))

def patches_list():
	prefix = 'Patch'
	root = globals().copy()
	r = []
	for k, v in root.items():
		if not inspect.isclass(v):
			continue
		if not k.startswith(prefix):
			continue
		if k == prefix:
			continue
		if not hasattr(v, 'name'):
			continue
		if not hasattr(v, 'description'):
			continue
		r.append(v)
	r.sort(key=lambda v: v.name)
	return r

def patches_filtered(enabled, disabled):
	all_patches = patches_list()
	r = []

	if enabled:
		set_e = set(enabled)
		for patch in all_patches:
			if patch.name in set_e:
				r.append(patch)
	elif disabled:
		set_d = set(disabled)
		for patch in all_patches:
			if not patch.name in set_d:
				r.append(patch)
	else:
		r = all_patches

	return r

def process(args):
	patches = patches_filtered(args.enabled, args.disabled)
	with open(args.file[0], 'rb+') as fp:
		for Patch in patches:
			fp.seek(0)
			print('Patching: %s: %s' % (Patch.name, Patch.description))
			Patch(fp).patch()
		fp.close()
	print('Done')

def main():
	# List all the patches for the help info.
	patches = patches_list()
	patches_help = []
	for patch in patches:
		patches_help.append('  %s %s' % (patch.name.ljust(21), patch.description))

	parser = argparse.ArgumentParser(
		description=os.linesep.join([
			'TLOMN Build 2001-10-23 Patcher',
			'Version: 1.6.0'
		]),
		epilog=os.linesep.join([
			'patches:',
			os.linesep.join(patches_help),
			'',
			'Copyright (c) 2018 JrMasterModelBuilder',
			'Licensed under the Mozilla Public License, v. 2.0'
		]),
		formatter_class=argparse.RawTextHelpFormatter
	)

	group_enable_disable = parser.add_mutually_exclusive_group()
	group_enable_disable.add_argument(
		'-e',
		'--enabled',
		action='append',
		help='Only apply listed patches'
	)
	group_enable_disable.add_argument(
		'-d',
		'--disabled',
		action='append',
		help='No not apply listed patches'
	)

	parser.add_argument(
		'file',
		nargs=1,
		help='File to be patched'
	)

	return process(parser.parse_args())

if __name__ == '__main__':
	sys.exit(main())
