help_string = """
Treehopper CLI Commands
────────────────────────────────────────────
  Main Server/Process commands
  ============================
  [treehopper | th] setup                                 Must run for setup the TH_ROOT directory structure and require files
  [treehopper | th] status                                Show if the main server is running
  [treehopper | th] start                                 Start the main server
  [treehopper | th] start --bg                            Start the main server in background
  [treehopper | th] stop                                  Stop the main server
  [treehopper | th] restart                               Restart main server
  [treehopper | th] list_agents                           List installed agents
  [treehopper | th] list_chains                           List installed chains
  [treehopper | th] clean                                 Be Careful - To cleanup the servers, pids, agents, chain

  Agent Related CLI Commands -
  ============================
  [treehopper | th] workspace create <n>                  Create empty directory
  [treehopper | th] workspace info                        Show current directory info
  [treehopper | th] push-file <agent-name> <file_path>    To push the input file to agent for any file operations
  [treehopper | th] call <path> '<json>' | --payload-file  Call an agent using the json payload or a json file
  [treehopper | th] init <agent_name>                     Create agent scaffold template
  [treehopper | th] lint <agent_folder>                   Validate handler.py + YAML
  [treehopper | th] build <agent_folder>                  Install agent to registry and run with main server
  [treehopper | th] agent info <ref>                      Show metadata
  [treehopper | th] agent start <name> --detached         Start dedicated agent runtime in background
  [treehopper | th] agent stop <name>                     Stop detached agent runtime
  [treehopper | th] agent delete <ref>                    Delete installed agent safely

  UI Related CLI Commands
  ==========================
  [treehopper | th] launch ui [optional --port <port>]     To launch the visualizer for the Agents, Chains, etc
  [treehopper | th] stop ui                                To stop the visualizer for the Agents, Chains, etc

  Chain Related CLI Commands
  ==========================
  [treehopper | th] chain                                 To view all Chain related commands
"""
