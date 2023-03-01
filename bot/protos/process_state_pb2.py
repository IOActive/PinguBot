# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: src/bot/protos/process_state.proto
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\"src/bot/protos/process_state.proto\"\x9f\x03\n\x11ProcessStateProto\x12\x17\n\x0ftime_date_stamp\x18\x01 \x01(\x03\x12\x1b\n\x13process_create_time\x18\r \x01(\x03\x12\'\n\x05\x63rash\x18\x02 \x01(\x0b\x32\x18.ProcessStateProto.Crash\x12\x11\n\tassertion\x18\x03 \x01(\t\x12\x19\n\x11requesting_thread\x18\x04 \x01(\x05\x12*\n\x07threads\x18\x05 \x03(\x0b\x32\x19.ProcessStateProto.Thread\x12\x1c\n\x07modules\x18\x06 \x03(\x0b\x32\x0b.CodeModule\x12\n\n\x02os\x18\x07 \x01(\t\x12\x10\n\x08os_short\x18\x08 \x01(\t\x12\x12\n\nos_version\x18\t \x01(\t\x12\x0b\n\x03\x63pu\x18\n \x01(\t\x12\x10\n\x08\x63pu_info\x18\x0b \x01(\t\x12\x11\n\tcpu_count\x18\x0c \x01(\x05\x1a(\n\x05\x43rash\x12\x0e\n\x06reason\x18\x01 \x02(\t\x12\x0f\n\x07\x61\x64\x64ress\x18\x02 \x02(\x03\x1a%\n\x06Thread\x12\x1b\n\x06\x66rames\x18\x01 \x03(\x0b\x32\x0b.StackFrame\"\x8e\x03\n\nStackFrame\x12\x13\n\x0binstruction\x18\x01 \x02(\x03\x12\x1b\n\x06module\x18\x02 \x01(\x0b\x32\x0b.CodeModule\x12\x15\n\rfunction_name\x18\x03 \x01(\t\x12\x15\n\rfunction_base\x18\x04 \x01(\x03\x12\x18\n\x10source_file_name\x18\x05 \x01(\t\x12\x13\n\x0bsource_line\x18\x06 \x01(\x05\x12\x18\n\x10source_line_base\x18\x07 \x01(\x03\x12%\n\x05trust\x18\x08 \x01(\x0e\x32\x16.StackFrame.FrameTrust\"\xaf\x01\n\nFrameTrust\x12\x14\n\x10\x46RAME_TRUST_NONE\x10\x00\x12\x14\n\x10\x46RAME_TRUST_SCAN\x10\x01\x12\x18\n\x14\x46RAME_TRUST_CFI_SCAN\x10\x02\x12\x12\n\x0e\x46RAME_TRUST_FP\x10\x03\x12\x13\n\x0f\x46RAME_TRUST_CFI\x10\x04\x12\x19\n\x15\x46RAME_TRUST_PREWALKED\x10\x05\x12\x17\n\x13\x46RAME_TRUST_CONTEXT\x10\x06\"\x9b\x01\n\nCodeModule\x12\x14\n\x0c\x62\x61se_address\x18\x01 \x01(\x03\x12\x0c\n\x04size\x18\x02 \x01(\x03\x12\x11\n\tcode_file\x18\x03 \x01(\t\x12\x17\n\x0f\x63ode_identifier\x18\x04 \x01(\t\x12\x12\n\ndebug_file\x18\x05 \x01(\t\x12\x18\n\x10\x64\x65\x62ug_identifier\x18\x06 \x01(\t\x12\x0f\n\x07version\x18\x07 \x01(\t')



_PROCESSSTATEPROTO = DESCRIPTOR.message_types_by_name['ProcessStateProto']
_PROCESSSTATEPROTO_CRASH = _PROCESSSTATEPROTO.nested_types_by_name['Crash']
_PROCESSSTATEPROTO_THREAD = _PROCESSSTATEPROTO.nested_types_by_name['Thread']
_STACKFRAME = DESCRIPTOR.message_types_by_name['StackFrame']
_CODEMODULE = DESCRIPTOR.message_types_by_name['CodeModule']
_STACKFRAME_FRAMETRUST = _STACKFRAME.enum_types_by_name['FrameTrust']
ProcessStateProto = _reflection.GeneratedProtocolMessageType('ProcessStateProto', (_message.Message,), {

  'Crash' : _reflection.GeneratedProtocolMessageType('Crash', (_message.Message,), {
    'DESCRIPTOR' : _PROCESSSTATEPROTO_CRASH,
    '__module__' : 'src.bot.protos.process_state_pb2'
    # @@protoc_insertion_point(class_scope:ProcessStateProto.Crash)
    })
  ,

  'Thread' : _reflection.GeneratedProtocolMessageType('Thread', (_message.Message,), {
    'DESCRIPTOR' : _PROCESSSTATEPROTO_THREAD,
    '__module__' : 'src.bot.protos.process_state_pb2'
    # @@protoc_insertion_point(class_scope:ProcessStateProto.Thread)
    })
  ,
  'DESCRIPTOR' : _PROCESSSTATEPROTO,
  '__module__' : 'src.bot.protos.process_state_pb2'
  # @@protoc_insertion_point(class_scope:ProcessStateProto)
  })
_sym_db.RegisterMessage(ProcessStateProto)
_sym_db.RegisterMessage(ProcessStateProto.Crash)
_sym_db.RegisterMessage(ProcessStateProto.Thread)

StackFrame = _reflection.GeneratedProtocolMessageType('StackFrame', (_message.Message,), {
  'DESCRIPTOR' : _STACKFRAME,
  '__module__' : 'src.bot.protos.process_state_pb2'
  # @@protoc_insertion_point(class_scope:StackFrame)
  })
_sym_db.RegisterMessage(StackFrame)

CodeModule = _reflection.GeneratedProtocolMessageType('CodeModule', (_message.Message,), {
  'DESCRIPTOR' : _CODEMODULE,
  '__module__' : 'src.bot.protos.process_state_pb2'
  # @@protoc_insertion_point(class_scope:CodeModule)
  })
_sym_db.RegisterMessage(CodeModule)

if _descriptor._USE_C_DESCRIPTORS == False:

  DESCRIPTOR._options = None
  _PROCESSSTATEPROTO._serialized_start=39
  _PROCESSSTATEPROTO._serialized_end=454
  _PROCESSSTATEPROTO_CRASH._serialized_start=375
  _PROCESSSTATEPROTO_CRASH._serialized_end=415
  _PROCESSSTATEPROTO_THREAD._serialized_start=417
  _PROCESSSTATEPROTO_THREAD._serialized_end=454
  _STACKFRAME._serialized_start=457
  _STACKFRAME._serialized_end=855
  _STACKFRAME_FRAMETRUST._serialized_start=680
  _STACKFRAME_FRAMETRUST._serialized_end=855
  _CODEMODULE._serialized_start=858
  _CODEMODULE._serialized_end=1013
# @@protoc_insertion_point(module_scope)
