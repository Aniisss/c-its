// generated from rosidl_generator_c/resource/idl__description.c.em
// with input from domain_bridge:msg/CompressedMsg.idl
// generated code does not contain a copyright notice

#include "domain_bridge/msg/detail/compressed_msg__functions.h"

ROSIDL_GENERATOR_C_PUBLIC_domain_bridge
const rosidl_type_hash_t *
domain_bridge__msg__CompressedMsg__get_type_hash(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static rosidl_type_hash_t hash = {1, {
      0x76, 0xde, 0x2b, 0x72, 0x98, 0x4e, 0xb5, 0x59,
      0x9a, 0xf6, 0x73, 0x90, 0xba, 0xa6, 0x94, 0x83,
      0x82, 0x35, 0xd8, 0xa8, 0x0b, 0x3b, 0xc7, 0x23,
      0x4f, 0x56, 0x95, 0x6e, 0xb6, 0xae, 0xd4, 0x66,
    }};
  return &hash;
}

#include <assert.h>
#include <string.h>

// Include directives for referenced types

// Hashes for external referenced types
#ifndef NDEBUG
#endif

static char domain_bridge__msg__CompressedMsg__TYPE_NAME[] = "domain_bridge/msg/CompressedMsg";

// Define type names, field names, and default values
static char domain_bridge__msg__CompressedMsg__FIELD_NAME__data[] = "data";

static rosidl_runtime_c__type_description__Field domain_bridge__msg__CompressedMsg__FIELDS[] = {
  {
    {domain_bridge__msg__CompressedMsg__FIELD_NAME__data, 4, 4},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_BYTE_UNBOUNDED_SEQUENCE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
};

const rosidl_runtime_c__type_description__TypeDescription *
domain_bridge__msg__CompressedMsg__get_type_description(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static bool constructed = false;
  static const rosidl_runtime_c__type_description__TypeDescription description = {
    {
      {domain_bridge__msg__CompressedMsg__TYPE_NAME, 31, 31},
      {domain_bridge__msg__CompressedMsg__FIELDS, 1, 1},
    },
    {NULL, 0, 0},
  };
  if (!constructed) {
    constructed = true;
  }
  return &description;
}

static char toplevel_type_raw_source[] =
  "byte[]  data";

static char msg_encoding[] = "msg";

// Define all individual source functions

const rosidl_runtime_c__type_description__TypeSource *
domain_bridge__msg__CompressedMsg__get_individual_type_description_source(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static const rosidl_runtime_c__type_description__TypeSource source = {
    {domain_bridge__msg__CompressedMsg__TYPE_NAME, 31, 31},
    {msg_encoding, 3, 3},
    {toplevel_type_raw_source, 12, 12},
  };
  return &source;
}

const rosidl_runtime_c__type_description__TypeSource__Sequence *
domain_bridge__msg__CompressedMsg__get_type_description_sources(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static rosidl_runtime_c__type_description__TypeSource sources[1];
  static const rosidl_runtime_c__type_description__TypeSource__Sequence source_sequence = {sources, 1, 1};
  static bool constructed = false;
  if (!constructed) {
    sources[0] = *domain_bridge__msg__CompressedMsg__get_individual_type_description_source(NULL),
    constructed = true;
  }
  return &source_sequence;
}
