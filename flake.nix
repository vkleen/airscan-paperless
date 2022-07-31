{
  inputs = {
    nixpkgs = {
      url = github:NixOS/nixpkgs;
    };
    poetry2nix = {
      url = github:nix-community/poetry2nix;
      inputs.nixpkgs.follows = "nixpkgs";
      inputs.flake-utils.follows = "flake-utils";
    };
    flake-utils = {
      url = github:numtide/flake-utils;
    };
  };

  outputs = { self, nixpkgs, ...}@inputs: {
    overlay = nixpkgs.lib.composeManyExtensions [
      inputs.poetry2nix.overlay
    ];
  } // (inputs.flake-utils.lib.eachDefaultSystem (system:
    let
      pkgs = import "${inputs.nixpkgs}/pkgs/top-level" {
        localSystem = { inherit system; };
        overlays = [ self.overlay ];
      };

      poetryOverrides = pkgs.poetry2nix.overrides.withDefaults (final: prev: {
        pyzbar = prev.pyzbar.overridePythonAttrs (_: {
          postPatch = ''
            substituteInPlace pyzbar/zbar_library.py \
              --replace \
                "find_library('zbar')" \
                '"${pkgs.lib.getLib pkgs.zbar}/lib/libzbar${pkgs.stdenv.hostPlatform.extensions.sharedLibrary}"'
          '';
        });
      });

      extraBuildInputs = [];

      poetryArgs = {
        projectDir = ./.;
        overrides = poetryOverrides;
      };

      airscan-paperless = pkgs.poetry2nix.mkPoetryApplication
        (poetryArgs // { propagatedBuildInputs = extraBuildInputs; });
      poetryShell = pkgs.poetry2nix.mkPoetryEnv poetryArgs;
    in rec {
      defaultPackage = packages.airscan-paperless;
      packages.airscan-paperless = airscan-paperless;

      devShell = pkgs.mkShell {
        inputsFrom = [ poetryShell.env ];
        buildInputs = [
          pkgs.pyright pkgs.poetry
        ] ++ extraBuildInputs;
      };
    }
  ));
}
