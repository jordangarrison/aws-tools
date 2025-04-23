{
  description = "AWS Tools – Collection of Python CLI utilities for AWS";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        py = pkgs.python313;
        pyPkgs = py.pkgs;

        # Common build inputs for Python applications
        commonBuildInputs = [
          pyPkgs.pdm-backend
          pyPkgs.setuptools
          pyPkgs.pip
          pyPkgs.wheel
        ];

        # ── Tool: DNS Upload Utility ────────────────────────────────────────────────
        dns-upload = pyPkgs.buildPythonApplication {
          pname = "dns-upload";
          version = "0.1.0";
          src = self;
          format = "pyproject";
          nativeBuildInputs = commonBuildInputs;
          propagatedBuildInputs = [
            pyPkgs.boto3
            pyPkgs.colorama
          ];
          # `doCheck = true` once you add unit tests
        };

        # Meta-package that includes all tools
        aws-tools-collection = pkgs.symlinkJoin {
          name = "aws-tools-collection";
          paths = [ dns-upload ];
          meta = {
            description = "Collection of AWS utility tools";
            mainProgram = "dns-upload";
          };
        };
      in
      {
        # ── Packages ────────────────────────────────────────────────────────────────
        packages = {
          default = aws-tools-collection;
          dns-upload = dns-upload;
          aws-tools-collection = aws-tools-collection;
        };

        # ── Apps (directly runnable) ────────────────────────────────────────────────
        apps = {
          default = flake-utils.lib.mkApp {
            drv = dns-upload;
            exePath = "/bin/dns-upload";
          };

          dns-upload = flake-utils.lib.mkApp {
            drv = dns-upload;
            exePath = "/bin/dns-upload";
          };
        };

        # ── Development shell ────────────────────────────────────────────────────────
        devShells.default = pkgs.mkShell {
          packages = [
            py
            pkgs.pdm
            pyPkgs.ipython
            pkgs.nixpkgs-fmt
            # Build dependencies
            pyPkgs.setuptools
            pyPkgs.pip
            pyPkgs.wheel
            # Runtime dependencies
            pyPkgs.boto3
            pyPkgs.colorama
          ];
          shellHook = ''
            export PDM_IGNORE_SAVED_PYTHON=1
            export PDM_PYTHON="${py}/bin/python"
            export PYTHONPATH="${py}/lib/python3.13/site-packages:$PYTHONPATH"
            echo "🔧 AWS Tools Dev Shell"
            echo "🔧 Python: ${py}/bin/python"
            echo "🔧 Available tools:"
            echo "  - dns-upload: Route53 DNS Records Bulk Upload Utility"
            echo ""
            echo "To run a tool: nix run .#[tool-name]"
            echo "To install a tool: nix profile install .#[tool-name]"
          '';
        };
      });
}
