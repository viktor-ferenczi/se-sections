using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;
using HarmonyLib;
using Sandbox;
using Sandbox.Engine.Physics;
using Sandbox.Game;
using Sandbox.Game.Entities;
using Sandbox.Game.Entities.Cube;
using Sandbox.Game.GameSystems.CoordinateSystem;
using Sandbox.Game.Gui;
using Sandbox.Game.GUI;
using Sandbox.Game.Multiplayer;
using Sandbox.Game.SessionComponents.Clipboard;
using Sandbox.Game.World;
using Sandbox.Graphics.GUI;
using Sandbox.ModAPI;
using VRage;
using VRage.Game;
using VRage.Input;
using VRage.Utils;
using VRageMath;
using VRageRender;
using IMyInput = VRage.Input.IMyInput;

namespace ClientPlugin.Logic
{
    public class Logic
    {
        public static readonly Logic Static = new Logic();

        private static bool eventHandlerRegistered;
        private static Config Cfg => Config.Current;

        // Reflection
        private static readonly MethodInfo ClearRenderData = AccessTools.DeclaredMethod(typeof(MyCubeBuilder), "ClearRenderData");
        private static readonly MethodInfo CheckCopyPasteAllowed = AccessTools.DeclaredMethod(typeof(MyClipboardComponent), "CheckCopyPasteAllowed");
        private static readonly FieldInfo ScreensField = AccessTools.DeclaredField(typeof(MyScreenManager), "m_screens");

        // Indexed by enum Base6Directions.Direction
        // MyControlsSpace.CUBE_ROTATE_VERTICAL_POSITIVE => MyKeys.PageDown
        // MyControlsSpace.CUBE_ROTATE_VERTICAL_NEGATIVE => MyKeys.Delete
        // MyControlsSpace.CUBE_ROTATE_HORISONTAL_POSITIVE => MyKeys.Home
        // MyControlsSpace.CUBE_ROTATE_HORISONTAL_NEGATIVE => MyKeys.End
        // MyControlsSpace.CUBE_ROTATE_ROLL_POSITIVE => MyKeys.Insert
        // MyControlsSpace.CUBE_ROTATE_ROLL_NEGATIVE => MyKeys.PageUp
        private static readonly MyStringId[] ResizeControls =
        {
            // Forward
            MyControlsSpace.CUBE_ROTATE_ROLL_NEGATIVE,
            // Backward
            MyControlsSpace.CUBE_ROTATE_VERTICAL_POSITIVE,
            // Left
            MyControlsSpace.CUBE_ROTATE_VERTICAL_NEGATIVE,
            // Right
            MyControlsSpace.CUBE_ROTATE_ROLL_POSITIVE,
            // Up
            MyControlsSpace.CUBE_ROTATE_HORISONTAL_POSITIVE,
            // Down
            MyControlsSpace.CUBE_ROTATE_HORISONTAL_NEGATIVE,
        };

        private enum State
        {
            Inactive,
            SelectingFirst,
            SelectingSecond,
            Resizing,
            TakingScreenshot,
            MovingThumbnail,
        }

        private State state;
        private MyCubeGrid grid;
        private MySlimBlock aimedBlock;
        private MySlimBlock firstBlock;
        private MySlimBlock secondBlock;
        private BoundingBoxI box;
        private BoundingBoxI originalBox;
        private string blueprintName;
        private string temporaryThumbnailPath;
        private string thumbnailPath;
        private DateTime startedMovingThumbnail;
        private int movingThumbnailProgress;

        public bool HandleGameInput()
        {
            if (!IsInActiveSession())
            {
                Reset();
                return false;
            }

            aimedBlock = GetAimedBlock();

            var input = MyInput.Static;
            switch (state)
            {
                case State.Inactive:
                    return HandleInactive(input);

                case State.SelectingFirst:
                    return HandleSelectingFirst(input);

                case State.SelectingSecond:
                    return HandleSelectingSecond(input);

                case State.Resizing:
                    return HandleResizing(input);

                case State.TakingScreenshot:
                    HandleTakingScreenshot();
                    return false;

                case State.MovingThumbnail:
                    return HandleMovingThumbnail(input);
            }

            return false;
        }

        private bool IsInActiveSession()
        {
            // Guard conditions
            return MySession.Static != null &&
                   MySession.Static.IsValid &&
                   MySession.Static.Ready &&
                   !MySession.Static.IsUnloading &&
                   (!Sync.MultiplayerActive || Sync.IsServer) &&
                   MyCubeBuilder.Static != null &&
                   MyInput.Static != null &&
                   MySandboxGame.Static != null &&
                   MyCoordinateSystem.Static != null &&
                   MyClipboardComponent.Static != null;
        }

        private bool HandleInactive(IMyInput input)
        {
            if (Cfg.Activate.IsPressed(input))
            {
                if (!(bool)CheckCopyPasteAllowed.Invoke(MyClipboardComponent.Static, Array.Empty<object>()))
                {
                    MyClipboardComponent.ShowCannotPasteError();
                    return true;
                }

                state = State.SelectingFirst;
                return true;
            }

            return false;
        }

        private bool HandleSelectingFirst(IMyInput input)
        {
            if (input.IsNewKeyPressed(MyKeys.Escape))
            {
                Reset();
                return true;
            }

            firstBlock = GetAimedBlock();
            grid = firstBlock?.CubeGrid;
            if (firstBlock == null || grid == null)
                return false;

            if (input.IsNewLeftMousePressed())
            {
                state = State.SelectingSecond;
                return true;
            }

            return false;
        }

        private bool HandleSelectingSecond(IMyInput input)
        {
            if (input.IsNewKeyPressed(MyKeys.Escape))
            {
                Reset();
                return true;
            }

            secondBlock = GetAimedBlock(grid);
            if (secondBlock == null)
                return false;

            CalculateBox();

            if (input.IsNewLeftMousePressed())
            {
                state = State.Resizing;
                return true;
            }

            return false;
        }

        private const string ConfigurationHint = "\r\n\r\nYou can disable this confirmation in configuration.\r\nTo configure, press Ctrl-Alt-/ after closing this dialog.";

        private bool HandleResizing(IMyInput input)
        {
            EnsureAimedBlockIsInsideSelection();

            if (input.IsNewKeyPressed(MyKeys.Escape))
            {
                Reset();
                return true;
            }

            if (input.IsNewLeftMousePressed())
            {
                var includeIntersectingBlocks = input.IsAnyCtrlKeyPressed();
                CopyToClipboard(includeIntersectingBlocks);
                Reset();
                return true;
            }

            if (input.IsNewRightMousePressed())
            {
                var includeIntersectingBlocks = input.IsAnyCtrlKeyPressed();
                if (Cfg.CutConfirmation)
                {
                    var messageBox = MyGuiSandbox.CreateMessageBox(
                        MyMessageBoxStyleEnum.Info,
                        MyMessageBoxButtonsType.YES_NO,
                        new StringBuilder("Are you sure to CUT the selected blocks?" + ConfigurationHint),
                        new StringBuilder("Confirmation - Box Selector"),
                        callback: result => { OnCutConfirmed(result, includeIntersectingBlocks); });
                    MyGuiSandbox.AddScreen(messageBox);
                }
                else
                {
                    OnCutConfirmed(MyGuiScreenMessageBox.ResultEnum.YES, includeIntersectingBlocks);
                }

                return true;
            }

            if (Cfg.SaveSelectedBlocks.IsPressed(input))
            {
                SaveToBlueprintFile(input.IsAnyCtrlKeyPressed());
                state = State.TakingScreenshot;
                return true;
            }

            if (Cfg.ResetSelection.IsPressed(input))
            {
                box = originalBox;
                return true;
            }

            if (Cfg.DeleteSelectedBlocks.IsPressed(input))
            {
                var includeIntersectingBlocks = input.IsAnyCtrlKeyPressed();
                if (Cfg.DeleteConfirmation)
                {
                    var messageBox = MyGuiSandbox.CreateMessageBox(
                        MyMessageBoxStyleEnum.Info,
                        MyMessageBoxButtonsType.YES_NO,
                        new StringBuilder("Are you sure to DELETE the selected blocks?" + ConfigurationHint),
                        new StringBuilder("Confirmation - Box Selector"),
                        callback: result => { OnDeleteConfirmed(result, includeIntersectingBlocks); });
                    MyGuiSandbox.AddScreen(messageBox);
                }
                else
                {
                    OnDeleteConfirmed(MyGuiScreenMessageBox.ResultEnum.YES, includeIntersectingBlocks);
                }

                return true;
            }

            var closestDirections = grid.WorldMatrix.FindClosestDirectionsTo(MyAPIGateway.Session.LocalHumanPlayer.Character.WorldMatrix);

            var b = box;
            var handled = false;
            var shift = input.IsAnyShiftKeyPressed();
            for (var directionIndex = 0; directionIndex < 6; directionIndex++)
            {
                var controlName = ResizeControls[directionIndex];
                var pressed = MyControllerHelper.IsControl(MyStringId.NullOrEmpty, controlName, MyControlStateType.NEW_PRESSED_REPEATING);
                if (!pressed)
                    continue;

                var direction = (Base6Directions.Direction)directionIndex;
                var step = closestDirections.GetClosestIntDirection(shift ? Base6Directions.GetOppositeDirection(direction) : direction);
                var axis = step.IndexOfFirstNonzeroAxis();

                if (shift == step[axis] > 0)
                    b.Min += step;
                else
                    b.Max += step;

                handled = true;
            }

            if (handled && b.IsValid)
                box = b;

            return handled;
        }

        private void HandleTakingScreenshot()
        {
            EnsureAimedBlockIsInsideSelection();
            TakeScreenshot();
        }

        private bool HandleMovingThumbnail(IMyInput input)
        {
            if (AttemptMovingThumbnail())
            {
                Reset();
                return true;
            }

            // Once progress is shown the operation is cancellable by the player
            if (movingThumbnailProgress != 0 && input.IsNewKeyPressed(MyKeys.Escape))
            {
                Reset();
                return true;
            }

            return false;
        }

        private void EnsureAimedBlockIsInsideSelection()
        {
            if (aimedBlock == null)
                return;

            if (!box.Intersects(new BoundingBoxI(aimedBlock.Min, aimedBlock.Max)))
                aimedBlock = null;
        }

        private void OnDeleteConfirmed(MyGuiScreenMessageBox.ResultEnum result, bool includeIntersectingBlocks)
        {
            if (result != MyGuiScreenMessageBox.ResultEnum.YES)
                return;

            DeleteBlocks(includeIntersectingBlocks);

            Reset();
        }

        private void OnCutConfirmed(MyGuiScreenMessageBox.ResultEnum result, bool includeIntersectingBlocks)
        {
            if (result != MyGuiScreenMessageBox.ResultEnum.YES)
                return;

            CopyToClipboard(includeIntersectingBlocks);
            DeleteBlocks(includeIntersectingBlocks);

            Reset();
        }

        private void Reset()
        {
            state = State.Inactive;
            grid = null;
            aimedBlock = null;
            firstBlock = null;
            secondBlock = null;
            box = BoundingBoxI.CreateInvalid();
            originalBox = BoundingBoxI.CreateInvalid();
            blueprintName = null;
            temporaryThumbnailPath = null;
            thumbnailPath = null;
            startedMovingThumbnail = DateTime.UtcNow;
            movingThumbnailProgress = 0;
        }

        private MySlimBlock GetAimedBlock(MyCubeGrid requiredGrid = null)
        {
            var placementProvider = MyCubeBuilder.PlacementProvider;
            var hitInfo = placementProvider.HitInfo;
            if (!hitInfo.HasValue)
                return null;

            var hitGrid = hitInfo.Value.HkHitInfo.GetHitEntity() as MyCubeGrid;
            if (hitGrid == null || (requiredGrid != null && hitGrid.EntityId != requiredGrid.EntityId))
                return null;

            var blockPosition = hitGrid.WorldToGridInteger(hitInfo.Value.Position + placementProvider.RayDirection * 1e-3);
            return hitGrid.GetCubeBlock(blockPosition);
        }

        private void CalculateBox()
        {
            box = new BoundingBoxI(Vector3I.Min(firstBlock.Min, secondBlock.Min), Vector3I.Max(firstBlock.Max, secondBlock.Max));
            originalBox = box;
        }

        private void DeleteBlocks(bool includeIntersectingBlocks)
        {
            var blockMinSet = CollectMinOfBlocksInBox(includeIntersectingBlocks);

            foreach (var min in blockMinSet)
            {
                grid.RemoveBlock(grid.GetCubeBlock(min), true);
            }

            grid.Physics.AddDirtyArea(box.Min, box.Max);
        }

        public bool DrawPrefix(MyCubeBuilder cubeBuilder)
        {
            if (!IsInActiveSession())
                return true;

            // Do not draw over the terminal
            if (MyGuiScreenTerminal.IsOpen)
                return true;

            // Do not draw over the Blueprints screen (F10)
            var screens = ScreensField.GetValue(null) as List<MyGuiScreenBase>;
            if (screens == null)
                return true;
            foreach (var screen in screens)
            {
                if (screen is MyGuiScreenGamePlay ||
                    screen is MyGuiScreenHudBase)
                    continue;

                var name = screen.GetType().Name;
                if (name == "MyGuiScreenDebugTiming" || // Compatibility with Shift-F11 statistics
                    name == "FPSOverlay") // Compatibility with the FPS Counter plugin
                    continue;

                return true;
            }

            switch (state)
            {
                case State.Inactive:
                    return true;

                case State.SelectingFirst:
                    ClearRenderData.Invoke(cubeBuilder, Array.Empty<object>());
                    MyCoordinateSystem.Static.Visible = true;
                    if (firstBlock != null)
                        DrawBlock(firstBlock, Cfg.FirstColor);
                    DrawHint("Select the first corner block", 2, x: 0.05f);
                    DrawHint("ESC: Cancel", 3, x: 0.05f);
                    DrawHint("Ctrl+Alt+/: Configure", 4, x: 0.05f);
                    break;

                case State.SelectingSecond:
                    MyCoordinateSystem.Static.Visible = true;
                    DrawBlock(firstBlock, Cfg.FirstColor);
                    if (secondBlock != null)
                    {
                        DrawBox(Cfg.BoxColor);
                        DrawBlock(secondBlock, Cfg.SecondColor);
                    }

                    DrawSize();
                    DrawHint("Select the second corner block", 2, x: 0.05f);
                    DrawHint("ESC: Cancel", 3, x: 0.05f);
                    DrawHint("Ctrl+Alt+/: Configure", 4, x: 0.05f);
                    break;

                case State.Resizing:
                    MyCoordinateSystem.Static.Visible = false;
                    DrawBox(Cfg.FinalBoxColor);
                    if (aimedBlock != null)
                        DrawBlock(aimedBlock, Cfg.AimedColor);
                    DrawSize();
                    DrawHint("Block rotation keys: Grow", 1, x: -0.1f);
                    DrawHint("+SHIFT to shrink the box", 2, x: -0.1f);
                    DrawHint("R: Restore original box", 3, x: -0.1f);
                    DrawHint("Ctrl+Alt+/: Configure", 4, x: -0.1f);
                    DrawHint("LMB: Copy    RMB: Cut", 1, x: 0.14f);
                    DrawHint("Backspace: Delete", 2, x: 0.14f);
                    DrawHint("ENTER: Save as a Section blueprint", 3, x: 0.14f);
                    DrawHint("+CTRL to include intersecting blocks", 4, x: 0.14f);
                    break;

                case State.TakingScreenshot:
                    MyCoordinateSystem.Static.Visible = false;
                    DrawBox(Cfg.FinalBoxColor);
                    if (aimedBlock != null)
                        DrawBlock(aimedBlock, Cfg.AimedColor);
                    break;

                case State.MovingThumbnail:
                    if (movingThumbnailProgress == 0)
                        break;
                    var progressBar = new string('.', movingThumbnailProgress);
                    DrawText($"Moving thumbnail{progressBar}", Cfg.HintColor, center: false, x: 0.40f, scale: 2f);
                    break;
            }

            return false;
        }

        private void DrawSize()
        {
            if (!Cfg.ShowSize)
                return;

            var text = GetSizeText(" x ");
            var scale = Cfg.SizeTextScale;
            DrawText(text, Cfg.SizeColor, scale: scale, y: -0.04f * scale);
        }

        private string GetSizeText(string separator)
        {
            var closestDirections = grid.WorldMatrix.FindClosestDirectionsTo(MyAPIGateway.Session.LocalHumanPlayer.Character.WorldMatrix);

            var xAxis = closestDirections.GetClosestIntDirection(Base6Directions.Direction.Right).IndexOfFirstNonzeroAxis();
            var yAxis = closestDirections.GetClosestIntDirection(Base6Directions.Direction.Up).IndexOfFirstNonzeroAxis();
            var zAxis = closestDirections.GetClosestIntDirection(Base6Directions.Direction.Backward).IndexOfFirstNonzeroAxis();

            var sz = box.Size + Vector3I.One;
            var text = $"{sz[xAxis]}{separator}{sz[yAxis]}{separator}{sz[zAxis]}";
            return text;
        }

        private void DrawHint(string text, int lineNumber, float x)
        {
            if (!Cfg.ShowHints)
                return;

            DrawText(text, Cfg.HintColor, lineNumber, center: false, x: 0.4f + x);
        }

        private void DrawText(string text, Color color, int lineNumber = 1, float scale = 1f, bool center = true, float x = 0.5f, float? y = null)
        {
            if (!y.HasValue)
                y = 0.04f * scale * (lineNumber - 1);

            var coords = new Vector2(MyRenderProxy.MainViewport.Width * x, MyRenderProxy.MainViewport.Height * (Cfg.TextPosition + y.Value));
            MyRenderProxy.DebugDrawText2D(coords, text, color, scale, center ? MyGuiDrawAlignEnum.HORISONTAL_CENTER_AND_VERTICAL_TOP : MyGuiDrawAlignEnum.HORISONTAL_LEFT_AND_VERTICAL_TOP);
        }

        private void DrawBlock(MySlimBlock block, Color color)
        {
            var v4Color = color.ToVector4();
            for (var i = 0; i < Cfg.HighlightDensity; i++)
            {
                MyCubeBuilder.DrawSemiTransparentBox(grid, block, v4Color, lineMaterial: Cfg.BlockMaterial, lineColor: v4Color);
            }
        }

        private void DrawBox(Color color)
        {
            var v4Color = color.ToVector4();
            for (var i = 0; i < Cfg.HighlightDensity; i++)
            {
                MyCubeBuilder.DrawSemiTransparentBox(box.Min, box.Max, grid, v4Color, lineMaterial: Cfg.BoxMaterial, lineColor: v4Color);
            }
        }

        private void CopyToClipboard(bool includeIntersectingBlocks)
        {
            var clipboard = MyClipboardComponent.Static?.Clipboard;
            if (clipboard == null)
                return;

            var gridBuilder = CreateGridBuilder(includeIntersectingBlocks);

            // Calculation copied from MyGuiBlueprintScreen_Reworked.CopyBlueprintPrefabToClipboard
            BoundingSphere boundingSphere = gridBuilder.CalculateBoundingSphere();
            MyPositionAndOrientation value = gridBuilder.PositionAndOrientation.Value;
            MatrixD m = MatrixD.CreateWorld(value.Position, value.Forward, value.Up);
            MatrixD m2 = MatrixD.Invert(m);
            Matrix matrix = Matrix.Normalize(m2);
            BoundingSphere boundingSphere2 = boundingSphere.Transform(m);
            Vector3 dragPointDelta = Vector3.TransformNormal((Vector3)(Vector3D)value.Position - boundingSphere2.Center, matrix);
            float dragVectorLength = boundingSphere.Radius + 10f;

            clipboard.SetGridFromBuilder(gridBuilder, dragPointDelta, dragVectorLength);
            clipboard.ShowModdedBlocksWarning = false;

            MyClipboardComponent.Static.Paste();
        }

        private static string BlueprintSubdirPath => Path.Combine(MyBlueprintUtils.BLUEPRINT_FOLDER_LOCAL, Cfg.SectionsSubdirectory);

        private void SaveToBlueprintFile(bool includeIntersectingBlocks)
        {
            var gridBuilder = CreateGridBuilder(includeIntersectingBlocks);

            // Clear the world position, so it is not exposed in multiplayer if the blueprint is shared.
            // The orientation is ignored on pasting, therefore it can be cleared as well.
            gridBuilder.PositionAndOrientation = MyPositionAndOrientation.Default;

            var blueprint = new MyObjectBuilder_ShipBlueprintDefinition();
            blueprint.DisplayName = gridBuilder.DisplayName;
            blueprint.CubeGrids = new[] { gridBuilder };

            var definition = new MyObjectBuilder_Definitions();
            definition.ShipBlueprints = new[] { blueprint };

            blueprintName = gridBuilder.DisplayName;
            Directory.CreateDirectory(BlueprintSubdirPath);
            MyBlueprintUtils.SavePrefabToFile(definition, blueprintName, Cfg.SectionsSubdirectory);
        }

        private MyObjectBuilder_CubeGrid CreateGridBuilder(bool includeIntersectingBlocks)
        {
            // Collect the Min coordinates of blocks considered to be inside the selection
            var blockMinSet = CollectMinOfBlocksInBox(includeIntersectingBlocks);

            // Keep only the blocks in selection by their Min coordinates
            var gridBuilder = (MyObjectBuilder_CubeGrid)grid.GetObjectBuilder();
            gridBuilder.CubeBlocks = gridBuilder.CubeBlocks.Where(b => blockMinSet.Contains(b.Min)).ToList();

            // Set the name, it will be the basis for saving the grid as a blueprint
            var sizeText = GetSizeText("x");
            gridBuilder.DisplayName = $"{gridBuilder.DisplayName} {sizeText}";

            // Sanity check
            if (gridBuilder.CubeBlocks.Count == 0)
                return gridBuilder;

            // Strip down block groups to contain only the blocks preserved
            foreach (var group in gridBuilder.BlockGroups)
            {
                group.Blocks = group.Blocks.Where(min => blockMinSet.Contains(min)).ToList();
            }

            // Remove empty block groups
            gridBuilder.BlockGroups = gridBuilder.BlockGroups.Where(group => group.Blocks.Count != 0).ToList();

            // Choose an origin block to allow for intuitive pasting of the copied grid or blueprint
            var originBlockMin = aimedBlock != null && blockMinSet.Contains(aimedBlock.Min)
                ? aimedBlock.Min
                : blockMinSet.FindCorner();
            var originBlockIndex = gridBuilder.CubeBlocks
                .FindIndex(b => (Vector3I)b.Min == originBlockMin);
            if (originBlockIndex <= 0)
                return gridBuilder;

            // Move the block to the head of the cube list, that marks it as the origin one 
            var originBlockBuilder = gridBuilder.CubeBlocks[originBlockIndex];
            gridBuilder.CubeBlocks.RemoveAt(originBlockIndex);
            gridBuilder.CubeBlocks.Insert(0, originBlockBuilder);

            return gridBuilder;
        }

        private HashSet<Vector3I> CollectMinOfBlocksInBox(bool includeIntersectingBlocks)
        {
            return grid.CubeBlocks
                .Where(block =>
                    includeIntersectingBlocks
                        ? box.Intersects(new BoundingBoxI(block.Min, block.Max))
                        : box.Contains(block.Min) == ContainmentType.Contains &&
                          box.Contains(block.Max) == ContainmentType.Contains)
                .Select(block => block.Min)
                .ToHashSet();
        }

        private void TakeScreenshot()
        {
            Debug.Assert(!string.IsNullOrEmpty(blueprintName));

            // Logic copied from MyGuiBlueprintScreen_Reworked.TakeScreenshotLocalBP
            float num = MyRenderProxy.MainViewport.Width / MyRenderProxy.MainViewport.Height;
            float num2 = (float)Math.Sqrt(262140f / num);
            Vector2 vector = new Vector2(num2 * num, num2);
            Vector2 sizeMultiplier = new Vector2(vector.X / MyRenderProxy.MainViewport.Width, vector.Y / MyRenderProxy.MainViewport.Height);
            if (sizeMultiplier.X > 1f)
            {
                sizeMultiplier.X = 1f;
            }

            if (sizeMultiplier.Y > 1f)
            {
                sizeMultiplier.Y = 1f;
            }

            if (!eventHandlerRegistered)
            {
                MySandboxGame.Static.OnScreenshotTaken += OnScreenshotTaken;
                eventHandlerRegistered = true;
            }

            temporaryThumbnailPath = Path.Combine(Constants.LocalTempDir, $"{MyBlueprintUtils.THUMB_IMAGE_NAME}.{Guid.NewGuid()}.png");
            MyRenderProxy.TakeScreenshot(sizeMultiplier, temporaryThumbnailPath, debug: false, ignoreSprites: true, showNotification: false);
        }

        public void SaveToDiskPostfix(string filePath)
        {
            if (string.IsNullOrEmpty(filePath) || !File.Exists(filePath))
                return;

            var actualBlueprintDir = Path.GetDirectoryName(filePath);
            if (actualBlueprintDir == null)
                return;

            thumbnailPath = Path.Combine(actualBlueprintDir, MyBlueprintUtils.THUMB_IMAGE_NAME);
        }

        private void OnScreenshotTaken(object sender, EventArgs e)
        {
            if (state != State.TakingScreenshot)
                return;

            startedMovingThumbnail = DateTime.UtcNow;
            state = State.MovingThumbnail;
        }

        private bool AttemptMovingThumbnail()
        {
            Debug.Assert(temporaryThumbnailPath != null);
            Debug.Assert(thumbnailPath != null);

            var elapsed = (DateTime.UtcNow - startedMovingThumbnail).TotalSeconds;
            movingThumbnailProgress = elapsed >= 1.5 ? (int)(1.5 * elapsed) : 0;

            if (elapsed > 5.0)
            {
                MyLog.Default.Warning($"{Plugin.Name}: Failed to move thumbnail file: {temporaryThumbnailPath} => {thumbnailPath}");
                return true;
            }

            if (!File.Exists(temporaryThumbnailPath))
            {
                // Wait for the file
                return false;
            }

            try
            {
                File.Move(temporaryThumbnailPath, thumbnailPath);
            }
            catch (IOException)
            {
                // Wait for the file being released (not locked by screenshot saving, antivirus, whatever)
                return false;
            }

            return true;
        }
    }
}