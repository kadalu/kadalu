#-*- mode: ruby -*-

# Build Containers
EMIT_STDOUT true do
  TEST "make build-containers"
end

# Show the list of Container images built
puts TEST "docker images"
