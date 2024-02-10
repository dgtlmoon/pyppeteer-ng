# Contribution Guidelines

Contributions are welcome as long as they follow core rule of this project:

The API of pyppeteer should [__match the API of puppeteer__](https://github.com/puppeteer/puppeteer) as closely as possible without sacrificing python too much.
ie keep public API keywords such as method names, arguments, class names etc. as they are in puppeteer version.

Other than that the contributions should remain as pythonic as possible and pass linting and code tests.
=======
The API of pyppeteer should __match the API of puppeteer__[1] as closely as possible without sacrificing Python too much.
- For public API items such as method names, property names, class names, an effort should be made to mirror the API
   if puppeteer. Where this is not possible, use a suitable substitute (eg `page.$eval` -> `page.Jeval`)
- For function arguments, most arguments can be translated 1:1, however there is a special case where puppeteer uses a
   single argument, `options` to workaround JS' lack of keyword arguments. In this case, `options` should be expanded
   appropriately based on the puppeteer source typings. For example:
```js
   /**
    * @param {number} x
    * @param {number} y
    * @param {!{delay?: number, button?: "left"|"right"|"middle", clickCount?: number}=} options
    */
   async click(x, y, options = {})
```
   Would become:
```python
    async def click(x, y, delay: float = None, button: str = None, clickCount: int = 1)
```
Pull requests should focus on one specific area where practical to aid in quick review. [pre-commit hooks](https://pre-commit.com/)
should be installed with `pre-commit install` to keep your code tidy.

Changes worthy of a changelog entry should get one - simply follow the existing format in CHANGELOG.md

## Maintainers - creating a release

 - Make sure all relevant changes have been recorded in the changelog
 - Ensure that code is properly tested
 - Bump the version in `pyproject.toml`, then tag the release in git
   - ex: `git tag -a 2.0.0rc1 -m "pypi release"`
 - Run `poetry build`
 - Run `poetry publish`
