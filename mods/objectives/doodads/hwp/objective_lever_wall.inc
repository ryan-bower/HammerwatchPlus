<!-- HWP objectives: a lever mounted on a wall (issue #74), HWPObjectiveSwitch (scripts/HWP/Objectives/Units.as)
     like the floor levers objective_switch.unit / objective_exit_switch.unit. One file per kind and wall:
     objective_switch_<n|e|w>.unit (kind "vault") and objective_exit_switch_<n|e|w>.unit (kind "exit") define
     WALL_N, WALL_E or WALL_W (and EXIT) and include this.

     The art is the vanilla wall pull lever's (doodads/buttons/button_wall_pull_n/e/w.unit): its "on" pose
     with the hint sparkle is our "left" (unused), its "use" animation, which holds the pulled pose, is our
     "right" (used). "marked" is "left" with the map icon (the Architect's Marked Switches; no icon
     otherwise, issue #26). The sounds are the floor lever's.

     Where the unit stands (Generation.as LeverInPfb; vanilla's wall buttons and torches stand the same way):
     - WALL_N, on the face of a wall with floor south of it: the wall cell's bottom edge, at its centre.
       The art is drawn up onto the face.
     - WALL_E, on a wall east of the floor: the wall's west edge; the art is drawn west of it, into the floor.
     - WALL_W, on a wall west of the floor: the wall's east edge; the art is drawn east of it.
     There is no south version: a wall south of the floor shows only its top, drawn two cells up over the
     floor in front of it (the walls' art, origin 0 32), so nothing on it can be seen (vanilla has none either).
     A sensor circle like a chest's adds it to the player's usables. -->
<unit slot="doodad">
	<behavior class="HWPObjectiveSwitch">
%if EXIT
		<string name="kind">exit</string>
%else
		<string name="kind">vault</string>
%endif
	</behavior>
	<scenes default="left" left="left" marked="marked" right="right">
		<scene name="shared">
%if WALL_N
			<sprite origin="5 30" texture="doodads/buttons/buttons.png" material="system/default.mats:proj-prop">
				<frame>34 145 10 12</frame>
			</sprite>
			<sprite origin="4 29" texture="doodads/buttons/buttons.png" material="system/default.mats:shadow">
				<frame>27 162 13 13</frame>
			</sprite>
%endif
%if WALL_E
			<sprite origin="7 30" texture="doodads/buttons/buttons.png" material="system/default.mats:proj-prop">
				<frame>44 144 7 18</frame>
			</sprite>
%endif
%if WALL_W
			<sprite origin="0 30" texture="doodads/buttons/buttons.png" material="system/default.mats:proj-prop">
				<frame>27 144 7 18</frame>
			</sprite>
%endif
			<collision static="true">
				<circle sensor="true" shoot-through="true" aim-through="true" offset="0 0" radius="18" />
			</collision>
		</scene>
		<scene name="left" trigger-snd="event:/sfx/doodads/buttons/lever_off">
			<scene src="shared" />
%if WALL_N
			<sprite origin="1 20" ulayer="1" texture="doodads/buttons/buttons.png" material="system/default.mats:proj-prop">
				<frame>3 144 3 12</frame>
			</sprite>
			<sprite origin="-1 16" texture="doodads/buttons/buttons.png" material="system/default.mats:shadow">
				<frame>21 144 3 12</frame>
			</sprite>
			<effect pos="0 -10" ulayer="2" src="doodads/buttons/hint.effect?a=1"/>
%endif
%if WALL_E
			<sprite origin="6 19" ulayer="1" texture="doodads/buttons/buttons.png" material="system/default.mats:proj-prop">
				<frame>12 144 3 12</frame>
			</sprite>
			<effect pos="-5 -9" ulayer="2" src="doodads/buttons/hint.effect?a=1"/>
%endif
%if WALL_W
			<sprite origin="-3 19" ulayer="1" texture="doodads/buttons/buttons.png" material="system/default.mats:proj-prop">
				<frame>12 144 3 12</frame>
			</sprite>
			<effect pos="4 -9" ulayer="2" src="doodads/buttons/hint.effect?a=1"/>
%endif
		</scene>
		<scene name="marked" trigger-snd="event:/sfx/doodads/buttons/lever_off">
			<scene src="left" />
			<scene src="special/minimap.unit:info_poi" />
		</scene>
		<scene name="right" trigger-snd="event:/sfx/doodads/buttons/lever_on">
			<scene src="shared" />
%if WALL_N
			<sprite origin="1 20" looping="false" ulayer="1" texture="doodads/buttons/buttons.png" material="system/default.mats:proj-prop">
				<frame time="60">3 144 3 12</frame>
				<frame time="60">0 156 3 15</frame>
				<frame time="60">6 171 3 20</frame>
				<frame time="60">3 171 3 20</frame>
			</sprite>
			<sprite origin="-1 16" looping="false" texture="doodads/buttons/buttons.png" material="system/default.mats:shadow">
				<frame time="60">21 144 3 12</frame>
				<frame time="60">18 156 3 15</frame>
				<frame time="60">24 171 3 16</frame>
				<frame time="60">21 171 3 16</frame>
			</sprite>
%endif
%if WALL_E
			<sprite origin="6 19" looping="false" ulayer="1" texture="doodads/buttons/buttons.png" material="system/default.mats:proj-prop">
				<frame time="60">12 144 3 12</frame>
				<frame time="60">9 156 3 15</frame>
				<frame time="60">15 171 3 18</frame>
				<frame time="60">12 171 3 18</frame>
			</sprite>
%endif
%if WALL_W
			<sprite origin="-3 19" looping="false" ulayer="1" texture="doodads/buttons/buttons.png" material="system/default.mats:proj-prop">
				<frame time="60">12 144 3 12</frame>
				<frame time="60">9 156 3 15</frame>
				<frame time="60">15 171 3 18</frame>
				<frame time="60">12 171 3 18</frame>
			</sprite>
%endif
		</scene>
	</scenes>
</unit>
