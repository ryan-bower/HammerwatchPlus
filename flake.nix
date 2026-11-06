{
  description = "Linux GameLab host tools (private Proton/Xvfb runtime)";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  outputs = { self, nixpkgs }: let
    system = "x86_64-linux";
    pkgs = import nixpkgs { inherit system; config.allowUnfree = true; };
    proton = pkgs.proton-ge-bin.steamcompattool;
    protonWine = pkgs.writeShellScript "gamelab-proton-wine" ''
      export WINESERVER=${proton}/files/bin/wineserver
      exec ${pkgs.steam-run}/bin/steam-run ${pkgs.python3}/bin/python3 ${proton}/proton run "$@"
    '';
    protonServer = pkgs.writeShellScript "gamelab-proton-server" ''
      exec ${pkgs.steam-run}/bin/steam-run ${proton}/files/bin/wineserver "$@"
    '';
  in {
    devShells.${system} = {
      default = self.devShells.${system}.proton;
      wine = pkgs.mkShell {
        packages = with pkgs; [ python3 uv git wineWow64Packages.stable xorg-server
          pkgsCross.mingwW64.stdenv.cc ];
        shellHook = ''
          unset HWP_PROTON
          export HWP_WINE="${pkgs.wineWow64Packages.stable}/bin/wine"
          export HWP_WINESERVER="${pkgs.wineWow64Packages.stable}/bin/wineserver"
          export HWP_XVFB="${pkgs.xorg-server}/bin/Xvfb"
        '';
      };
      proton = pkgs.mkShell {
        packages = with pkgs; [ python3 uv git xorg-server pkgsCross.mingwW64.stdenv.cc ];
        shellHook = ''
          export HWP_WINE="${protonWine}"
          export HWP_WINESERVER="${protonServer}"
          export HWP_PROTON=1
          export HWP_XVFB="${pkgs.xorg-server}/bin/Xvfb"
        '';
      };
    };
  };
}
