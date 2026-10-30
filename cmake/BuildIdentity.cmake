# Capture the source repository at configure time. A source archive must not
# inherit the identity of an unrelated enclosing checkout.
function(g4usim_capture_build_identity source_root input_files commit_var state_var)
    set(commit "unknown")
    set(state "unknown")
    find_package(Git QUIET)
    if(GIT_FOUND AND EXISTS "${source_root}/.git")
        execute_process(COMMAND "${GIT_EXECUTABLE}" rev-parse --show-toplevel
            WORKING_DIRECTORY "${source_root}" RESULT_VARIABLE root_result
            OUTPUT_VARIABLE git_root OUTPUT_STRIP_TRAILING_WHITESPACE ERROR_QUIET)
        get_filename_component(expected_root "${source_root}" REALPATH)
        get_filename_component(git_root "${git_root}" REALPATH)
        if(WIN32)
            string(TOLOWER "${expected_root}" expected_root)
            string(TOLOWER "${git_root}" git_root)
        endif()
        if(root_result EQUAL 0 AND git_root STREQUAL expected_root)
            execute_process(COMMAND "${GIT_EXECUTABLE}" rev-parse --verify HEAD
                WORKING_DIRECTORY "${source_root}" RESULT_VARIABLE head_result
                OUTPUT_VARIABLE candidate OUTPUT_STRIP_TRAILING_WHITESPACE ERROR_QUIET)
            string(LENGTH "${candidate}" candidate_length)
            if(head_result EQUAL 0 AND candidate MATCHES "^[0-9a-f]+$" AND
               (candidate_length EQUAL 40 OR candidate_length EQUAL 64))
                set(commit "${candidate}")
                set(relative_inputs "")
                foreach(input_file IN LISTS input_files)
                    file(RELATIVE_PATH input_name "${source_root}" "${input_file}")
                    list(APPEND relative_inputs "${input_name}")
                endforeach()
                # Git status honors assume-unchanged/skip-worktree and ignores
                # some untracked inputs. Compare actual raw blobs to HEAD instead.
                execute_process(COMMAND "${GIT_EXECUTABLE}" hash-object --no-filters -- ${relative_inputs}
                    WORKING_DIRECTORY "${source_root}" RESULT_VARIABLE hash_result
                    OUTPUT_VARIABLE actual_hashes OUTPUT_STRIP_TRAILING_WHITESPACE ERROR_QUIET)
                execute_process(COMMAND "${GIT_EXECUTABLE}" --literal-pathspecs -c core.quotepath=false
                    ls-tree -r --full-tree "--format=%(objectname) %(path)" HEAD -- ${relative_inputs}
                    WORKING_DIRECTORY "${source_root}" RESULT_VARIABLE tree_result
                    OUTPUT_VARIABLE head_manifest OUTPUT_STRIP_TRAILING_WHITESPACE ERROR_QUIET)
                if(hash_result EQUAL 0 AND tree_result EQUAL 0)
                    string(REPLACE "\n" ";" actual_hashes "${actual_hashes}")
                    list(LENGTH actual_hashes hash_count)
                    list(LENGTH relative_inputs input_count)
                    if(hash_count EQUAL input_count)
                        set(actual_manifest "")
                        math(EXPR last_input "${input_count}-1")
                        foreach(index RANGE ${last_input})
                            list(GET relative_inputs ${index} input_name)
                            list(GET actual_hashes ${index} input_hash)
                            list(APPEND actual_manifest "${input_hash} ${input_name}")
                        endforeach()
                        string(REPLACE "\n" ";" head_manifest "${head_manifest}")
                        list(SORT actual_manifest)
                        list(SORT head_manifest)
                        if(actual_manifest STREQUAL head_manifest)
                            set(state "clean")
                        else()
                            set(state "dirty")
                        endif()
                    endif()
                endif()
            endif()
            # A documentation-only commit still changes this executable's
            # recorded commit on the next incremental build.
            execute_process(COMMAND "${GIT_EXECUTABLE}" symbolic-ref -q HEAD
                WORKING_DIRECTORY "${source_root}" OUTPUT_VARIABLE branch_ref
                OUTPUT_STRIP_TRAILING_WHITESPACE ERROR_QUIET)
            foreach(git_name HEAD index packed-refs "${branch_ref}")
                if(NOT git_name STREQUAL "")
                    execute_process(COMMAND "${GIT_EXECUTABLE}" rev-parse --git-path "${git_name}"
                        WORKING_DIRECTORY "${source_root}" RESULT_VARIABLE path_result
                        OUTPUT_VARIABLE git_path OUTPUT_STRIP_TRAILING_WHITESPACE ERROR_QUIET)
                    if(path_result EQUAL 0)
                        get_filename_component(git_path "${git_path}" ABSOLUTE BASE_DIR "${source_root}")
                        if(EXISTS "${git_path}")
                            set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${git_path}")
                        endif()
                    endif()
                endif()
            endforeach()
        endif()
    endif()
    set(${commit_var} "${commit}" PARENT_SCOPE)
    set(${state_var} "${state}" PARENT_SCOPE)
endfunction()
