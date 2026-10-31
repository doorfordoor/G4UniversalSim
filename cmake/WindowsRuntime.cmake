# This module is part of the existing *.cmake build fingerprint. Generate the
# manifest in the build tree so it cannot be omitted from source identity.
function(g4usim_configure_windows_runtime target)
    if(WIN32 AND MSVC)
        set(runtime_manifest "${CMAKE_CURRENT_BINARY_DIR}/${target}.manifest")
        file(WRITE "${runtime_manifest}" [=[<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
  <application xmlns="urn:schemas-microsoft-com:asm.v3">
    <windowsSettings>
      <longPathAware xmlns="http://schemas.microsoft.com/SMI/2016/WindowsSettings">true</longPathAware>
      <activeCodePage xmlns="http://schemas.microsoft.com/SMI/2019/WindowsSettings">UTF-8</activeCodePage>
    </windowsSettings>
  </application>
</assembly>
]=])
        target_sources(${target} PRIVATE "${runtime_manifest}")
    endif()
endfunction()
