// Read-only health sampling: unlike PlayerDamagedActor, this sees affliction
// ticks and replicated damage too. In co-op the figure is the dummy's total,
// not a claim about one player's contribution. Never changes combat or saves.
namespace HWP
{
	namespace DummyDPS
	{
		const uint WINDOW_MS = 5000;
		const int RADIUS = 600;
		const uint MAX_DUMMIES = 32;

		bool Enabled() { return HWP::Settings::GetBool("dummydps.enabled", true); }
		Modules::HWPDummyDPSModule@ g_module;

		void Command(array<string>@ args)
		{
			if (args.length() > 0 && args[0] == "selftest")
			{
				Window w;
				bool ok = w.DPS(0) == 0;
				w.Add(100, 500);
				w.Add(100, 250);
				w.Add(1100, 250);
				w.Add(1100, -900); // healing / no damage
				ok = ok && w.samples.length() == 2 && w.DPS(5099) == 200;
				ok = ok && w.DPS(5100) == 50 && w.DPS(6100) == 0;
				Window other;
				other.Add(0, 1000);
				ok = ok && other.DPS(0) == 200 && w.DPS(6100) == 0;
				Window wrap;
				wrap.Add(0xffffff00, 500);
				ok = ok && wrap.DPS(0x00000010) == 100 && wrap.DPS(0x00001288) == 0;
				HWP::Log("dummydps", "window selftest " + (ok ? "PASS" : "FAIL"));
				return;
			}
			if (g_module !is null)
				g_module.Report();
		}

		class Sample
		{
			uint time;
			double damage;
		}

		class Window
		{
			array<Sample@> samples;
			double sum = 0;

			void Expire(uint now)
			{
				while (samples.length() > 0 && uint(now - samples[0].time) >= WINDOW_MS)
				{
					sum -= samples[0].damage;
					samples.removeAt(0);
				}
				if (samples.length() == 0)
					sum = 0;
			}

			void Add(uint now, double damage)
			{
				Expire(now);
				if (damage <= 0)
					return;
				// At most one entry per game millisecond: bounded even at high FPS.
				if (samples.length() > 0 && samples[samples.length() - 1].time == now)
					samples[samples.length() - 1].damage += damage;
				else
				{
					Sample s;
					s.time = now;
					s.damage = damage;
					samples.insertLast(s);
				}
				sum += damage;
			}

			double DPS(uint now)
			{
				Expire(now);
				return sum / 5.0;
			}
		}

		class Dummy
		{
			UnitPtr unit;
			double previous;
			int maxHp;
			Window window;
			BitmapString@ text;
		}

		bool IsDummy(Actor@ actor)
		{
			return actor !is null && (actor.Tags & ApplyTag(0, g_actorTags.GetTag("target_dummy"))) != 0;
		}
	}
}

namespace Modules
{
	class HWPDummyDPSModule : Module
	{
		array<HWP::DummyDPS::Dummy@> m_dummies;
		uint m_clock = 0;
		int m_scan = 0;
		int m_text = 0;

		HWPDummyDPSModule()
		{
			super("hwp-dummydps");
			@HWP::DummyDPS::g_module = this;
			HWP::Commands::Register("dummydps", "[selftest]  show nearby dummy DPS or check the rolling window", HWP::Commands::Handler(HWP::DummyDPS::Command));
		}

		void Report()
		{
			HWP::Log("dummydps", "tracked=" + m_dummies.length());
			for (uint i = 0; i < m_dummies.length(); i++)
			{
				auto d = m_dummies[i];
				HWP::Log("dummydps", "unit=" + d.unit.GetId() + " dps=" + formatFloat(d.window.DPS(m_clock), "", 0, 0) + " text=" + (d.text !is null ? "yes" : "no"));
			}
		}

		void Discover(vec2 at)
		{
			auto results = g_scene.QueryCircle(at, HWP::DummyDPS::RADIUS, ~0, RaycastType::Any, true);
			for (uint i = 0; i < results.length() && m_dummies.length() < HWP::DummyDPS::MAX_DUMMIES; i++)
			{
				UnitPtr unit = results[i];
				auto actor = cast<Actor>(unit.GetScriptBehavior());
				if (!HWP::DummyDPS::IsDummy(actor) || actor.IsDead())
					continue;
				bool known = false;
				for (uint j = 0; j < m_dummies.length(); j++)
					if (m_dummies[j].unit == unit)
						known = true;
				if (known)
					continue;
				HWP::DummyDPS::Dummy d;
				d.unit = unit;
				d.maxHp = actor.GetMaxHp();
				d.previous = double(actor.GetHealth()) * double(d.maxHp);
				m_dummies.insertLast(d);
			}
		}

		// HWP::Guard (tools/guard_modules.py): a script error here turns this off, not the game
		HWP::Guard m_guardUpdateFrame;
		void UpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused) override
		{
			if (m_guardUpdateFrame.Skip("dummydps", "HWPDummyDPSModule.UpdateFrame"))
				return;
			if (m_guardUpdateFrame.Raw())
			{
				GuardedUpdateFrame(ms, gameInput, menuInput, paused);
				m_guardUpdateFrame.Ok();
				return;
			}
			try { GuardedUpdateFrame(ms, gameInput, menuInput, paused); m_guardUpdateFrame.Ok(); }
			catch { m_guardUpdateFrame.Failed(); }
		}

		void GuardedUpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused)
		{
			if (!HWP::DummyDPS::Enabled() || cast<TownGameMode>(g_gameMode) is null)
			{
				m_dummies.resize(0);
				m_scan = 0;
				return;
			}
			if (paused)
				return;
			auto rec = GetLocalPlayerRecord();
			if (rec is null || rec.actor is null)
				return;
			vec2 at = xy(rec.actor.m_unit.GetPosition());
			m_clock += uint(max(0, ms));
			m_scan -= ms;
			m_text -= ms;
			for (int i = int(m_dummies.length()) - 1; i >= 0; i--)
			{
				auto d = m_dummies[i];
				if (!d.unit.IsValid() || d.unit.IsDestroyed() || dist(at, xy(d.unit.GetPosition())) > HWP::DummyDPS::RADIUS)
				{
					m_dummies.removeAt(i);
					continue;
				}
				auto actor = cast<Actor>(d.unit.GetScriptBehavior());
				if (actor is null || actor.IsDead() || actor.GetMaxHp() != d.maxHp)
				{
					m_dummies.removeAt(i);
					continue;
				}
				double hp = double(actor.GetHealth()) * double(d.maxHp);
				d.window.Add(m_clock, d.previous - hp);
				d.previous = hp; // healing is never counted as negative damage
				if (m_text <= 0 || d.text is null)
				{
					string label = Resources::GetString(".hwp.dummydps.label").replace("%dps%", formatFloat(d.window.DPS(m_clock), "", 0, 0));
					auto font = Resources::GetBitmapFont("gui/fonts/arial11.fnt");
					@d.text = font.BuildText(label, -1, TextAlignment::Center, vec4(1, 0.9f, 0.4f, 1));
				}
			}
			if (m_scan <= 0)
			{
				Discover(at);
				m_scan = 250;
			}
			if (m_text <= 0)
				m_text = 250;
		}

		// HWP::Guard (tools/guard_modules.py): a script error here turns this off, not the game
		HWP::Guard m_guardRenderFrame;
		void RenderFrame(int idt, SpriteBatch& sb) override
		{
			if (m_guardRenderFrame.Skip("dummydps", "HWPDummyDPSModule.RenderFrame"))
				return;
			if (m_guardRenderFrame.Raw())
			{
				GuardedRenderFrame(idt, sb);
				m_guardRenderFrame.Ok();
				return;
			}
			try { GuardedRenderFrame(idt, sb); m_guardRenderFrame.Ok(); }
			catch { m_guardRenderFrame.Failed(); }
		}

		void GuardedRenderFrame(int idt, SpriteBatch& sb)
		{
			if (!HWP::DummyDPS::Enabled() || cast<TownGameMode>(g_gameMode) is null)
				return;
			for (uint i = 0; i < m_dummies.length(); i++)
			{
				auto d = m_dummies[i];
				if (d.text is null || !d.unit.IsValid() || d.unit.IsDestroyed())
					continue;
				vec2 at = ToScreenspace(d.unit.GetInterpolatedPosition(idt) + vec3(0, -38, 0)) / g_gameMode.m_wndScale;
				sb.FillRectangle(vec4(int(at.x - d.text.GetWidth() / 2 - 3), int(at.y - 1), d.text.GetWidth() + 6, d.text.GetHeight() + 2), vec4(0, 0, 0, 0.75f));
				sb.DrawString(vec2(int(at.x), int(at.y)), d.text);
			}
		}
	}
}
