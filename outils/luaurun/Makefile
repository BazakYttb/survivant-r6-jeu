# Dossier des sources de Luau 0.740 (https://github.com/luau-lang/luau) : make L=/chemin/vers/luau
L ?= ../luau
SRCS := $(wildcard $(L)/Ast/src/*.cpp $(L)/Bytecode/src/*.cpp $(L)/Common/src/*.cpp $(L)/Compiler/src/*.cpp $(L)/VM/src/*.cpp) main.cpp
OBJS := $(patsubst %.cpp,obj/%.o,$(notdir $(SRCS)))
CXXFLAGS := -std=c++17 -O1 -fno-math-errno -I$(L)/Common/include -I$(L)/Ast/include -I$(L)/Bytecode/include -I$(L)/Compiler/include -I$(L)/VM/include -I$(L)/VM/src -I$(L)/Bytecode/src '-DLUA_API=extern "C"' '-DLUACODE_API=extern "C"' -DLUA_VECTOR_SIZE=3
vpath %.cpp $(L)/Ast/src $(L)/Bytecode/src $(L)/Common/src $(L)/Compiler/src $(L)/VM/src .
luaurun: $(OBJS)
	$(CXX) $(OBJS) -o $@
obj/%.o: %.cpp
	@mkdir -p obj
	nice $(CXX) $(CXXFLAGS) -c $< -o $@
