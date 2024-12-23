using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Text;
using Sandbox.Game.Entities.Cube;
using Group = System.Collections.Generic.Dictionary<string, string>;

namespace ClientPlugin.Logic
{
    public class DataStorage
    {
        public readonly MyTerminalBlock TerminalBlock;
        public string Guid { get; private set; }
        protected readonly Dictionary<string, Group> Groups = new Dictionary<string, Group>();

        protected DataStorage(MyTerminalBlock terminalBlock)
        {
            if (terminalBlock.Closed || terminalBlock.CubeGrid == null || terminalBlock.CubeGrid.Closed)
                return;

            TerminalBlock = terminalBlock;

            if (!terminalBlock.TryGetStorage(out var data))
            {
                GenerateNewGuid();
                WriteStorage();
                return;
            }

            ParseStorage(data);

            if (Guid == null)
            {
                // Ignore broken data from storage, re-initialize with a new GUID
                Groups.Clear();
                GenerateNewGuid();
                WriteStorage();
            }
        }

        public void GenerateNewGuid()
        {
            Guid = System.Guid.NewGuid().ToString();
        }

        private void ParseStorage(string data)
        {
            Group group = null;
            foreach (var line in data.Split('\n'))
            {
                var item = line.Trim();
                if (item.Length == 0)
                    continue;

                if (item.StartsWith("[") && item.EndsWith("]"))
                {
                    string groupName = item.Substring(1, item.Length - 2);
                    Groups[groupName] = group = new Group();
                    continue;
                }

                if (group == null)
                {
                    if (Guid != null)
                    {
                        // Broken, ignore the data from storage
                        Guid = null;
                        break;
                    }

                    Guid = item;
                }
                else
                {
                    var i = item.IndexOf(':');
                    var key = i >= 0 ? item.Substring(0, i) : "";
                    var value = i >= 0 ? item.Substring(i + 1) : "";
                    group[key] = value;
                }
            }
        }

        public void WriteStorage()
        {
            if (TerminalBlock == null)
                return;

            var data = new StringBuilder();
            data.AppendLine(Guid);

            foreach (var (groupName, items) in Groups)
            {
                data.AppendLine("");
                data.AppendLine($"[{groupName}]");
                foreach (var item in items)
                    data.AppendLine($"{item.Key}:{item.Value}");
            }

            TerminalBlock.SetStorage(data.ToString());
        }
    }
}