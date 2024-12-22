using Sandbox.Graphics.GUI;
using System;
using System.Collections.Generic;
using VRage.Utils;
using VRageMath;

namespace ClientPlugin.Settings.Elements
{
    internal class SeparatorAttribute : Attribute, IElement
    {
        public readonly string Caption;

        public SeparatorAttribute(string caption = null)
        {
            Caption = caption;
        }

        public List<Control> GetControls(string name, Func<object> propertyGetter, Action<object> propertySetter)
        {
            var label = new MyGuiControlLabel(text: Caption ?? "")
            {
                // Size = new Vector2(0.5f, 0.04f),
                ColorMask = Color.Orange,
            };

            var c = Color.LightCyan;
            var line = new MyGuiControlLabel
            {
                Size = new Vector2(0.5f, 0f),
                BorderEnabled = true,
                BorderSize = 1,
                BorderColor = new Color(c.R,c.G,c.B,0.1f),
            };

            return new List<Control>()
            {
                new Control(label, rightMargin: 0.005f),
                new Control(line, fillFactor: 1f, offset: new Vector2(0f, 0.003f)),
            };
        }

        public List<Type> SupportedTypes { get; } = new List<Type>()
        {
            typeof(object)
        };
    }
}