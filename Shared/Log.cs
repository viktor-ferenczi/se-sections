using VRage.Utils;

namespace Shared
{
    public static class Log
    {
        public const string Name = "Sections";

        // Not MyLog's Info/Warning/Error: those format the message, braces in it would throw
        public static void Info(string message) => Write("Info", message);

        public static void Warning(string message) => Write("Warning", message);

        public static void Error(string message) => Write("Error", message);

        private static void Write(string level, string message) =>
            MyLog.Default?.WriteLineAndConsole($"{Name}: {level}: {message}");
    }
}
