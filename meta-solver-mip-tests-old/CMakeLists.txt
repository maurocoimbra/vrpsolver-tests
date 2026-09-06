cmake_minimum_required(VERSION 3.15)

project(MeuProjeto)

set(CMAKE_CXX_STANDARD 17)

# Executável

add_executable(MeuProjeto
src/main.cpp
)

# Diretório dos headers da biblioteca

target_include_directories(MeuProjeto PRIVATE
"C:/dev/rcsp/include_dev"
)

# Diretório onde está a .lib

target_link_directories(MeuProjeto PRIVATE
"C:/dev/rcsp/build/lib/Release"
)

# Linkar biblioteca

target_link_libraries(MeuProjeto PRIVATE
rcsp
)