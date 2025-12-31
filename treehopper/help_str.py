help_string = """
Treehopper CLI Commands
────────────────────────────────────────────
  Main Server/Process commands
  ============================
  [treehopper | th] setup                                 Must run for setup the TH_ROOT directory structure and require files
  [treehopper | th] workspace create <n>                  Create empty directory
  [treehopper | th] workspace info                        Show current directory info
  [treehopper | th] status                                Show if the main server is running
  [treehopper | th] start                                 Start the main server
  [treehopper | th] start --bg                            Start the main server in background
  [treehopper | th] stop                                  Stop the main server
  [treehopper | th] restart                               Restart main server
  [treehopper | th] list_agents                           List installed agents
  [treehopper | th] list_chains                           List installed chains

  Push file to root for input
  ============================
  [treehopper | th] push-file <agent-name> <file_path>    To push the input file to agent for any file operations

  Agent Related CLI Commands -
  ============================
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

  System Inspection Commands
  ==========================
  [treehopper | th] show root                          Show full TH_ROOT directory structure as a tree
  [treehopper | th] show pids                          List all active process IDs and assigned ports

  DB Related CLI Commands
  ==========================
  [treehopper | th] view db --show-tables                 List all database tables and row counts
  [treehopper | th] view db --show-tables --json          List tables and counts in JSON format
  [treehopper | th] view db --show-tables --plain         List tables in a clean key-value list (no boxes)

  [treehopper | th] view db --table <name>                View content of a specific table
  [treehopper | th] view db --table <name> --plain        View table in a clean key-value list (no boxes)
  [treehopper | th] view db --table <name> --json         Valid JSON array of agent records
  [treehopper | th] view db --table <name> --limit <n>    View table with custom row limit
  [treehopper | th] view db --table <name> -s <query>     Search for a string across all columns in a table

  [treehopper | th] view db --all                         Full inspection (latest 100 records for all tables)
  [treehopper | th] view db --all --limit <number>        Dumps the last 10 records of every table.

  Log Related CLI Commands (Local Time)
  =====================================
  [treehopper | th] view logs                             Show latest 50 log entries in local time
  [treehopper | th] view logs --tail <n>                  Show latest <n> log entries
  [treehopper | th] view logs --level <LVL>               Filter logs by level (INFO, ERROR, DEBUG)
  [treehopper | th] view logs --all                       Dump all historical logs from the log directory

  Template Related CLI Commands
  =============================
  [treehopper | th] template lint <template_name>         Check template is correctly structured
  [treehopper | th] template deploy <template_name>       Deploy will add your unique template or overwrite existing to folder treehopper/agent_templates
  [treehopper | th] template view <template_name>         View your template
  [treehopper | th] template list                         List all templates
  [treehopper | th] template delete <template_name>       [!Be Careful] Hard Delete template

  [! BE CAREFUL] Maintainance CLI Commands
  =========================================
  [treehopper | th] admin snapshot-db        Snapshot analytics DB
  [treehopper | th] admin prune-db           Prune analytics DB (retention policy)
  [treehopper | th] admin rotate-files       Rotate runtime files (.log, .jsonl, .cancel, etc)
  [treehopper | th] admin cleanup-archives   Remove expired archives
  [treehopper | th] admin storage            Show storage metrics

  [! BE CAREFUL] Full Cleanup
  ============================
  [treehopper | th] clean                                 Be Careful - To cleanup the servers, pids, agents, chain


"""
